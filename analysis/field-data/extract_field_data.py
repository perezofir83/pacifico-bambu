#!/usr/bin/env python3
"""
Extract topography, rainfall, and vegetation health for Pacifico Bambu fields.

Data sources (all free, no commercial account required):
  - Topography: Copernicus DEM 30m via Microsoft Planetary Computer
  - Vegetation: Sentinel-2 L2A 10m via Microsoft Planetary Computer
  - Rainfall: CHIRPS monthly TIFs via direct HTTP from UCSB CHC server

Outputs: CSVs + Hebrew Markdown summary in outputs/.
"""

import sys
import csv
import io
import gzip
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from urllib.request import urlopen, Request

import numpy as np
import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import shape, mapping, box as shp_box
import rasterio
from rasterio.io import MemoryFile
from rasterio.mask import mask as rio_mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

import pystac_client
import planetary_computer
import stackstac
import rioxarray
import xarray as xr

fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

SCRIPT_DIR = Path(__file__).parent
FIELDS_DIR = SCRIPT_DIR / 'fields'
OUT_DIR = SCRIPT_DIR / 'outputs'
CACHE_DIR = SCRIPT_DIR / '.cache'
OUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

FIELDS = [
    ('first_field', FIELDS_DIR / 'first_field.kml', 'Guadua 6 שנים'),
    ('second_field', FIELDS_DIR / 'second_field.kml', 'Guadua שדה 2'),
]

S2_START = '2017-01-01'
S2_END = '2026-04-30'
CHIRPS_START_YEAR = 2016
CHIRPS_END_YEAR = 2025
UTM_CRS = 'EPSG:32614'  # UTM 14N - Oaxaca

WET_MONTHS = [5, 6, 7, 8, 9, 10]
DRY_MONTHS = [11, 12, 1, 2, 3, 4]

STAC_URL = 'https://planetarycomputer.microsoft.com/api/stac/v1'
CHIRPS_URL_TEMPLATE = (
    'https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/'
    'chirps-v2.0.{year}.{month:02d}.tif.gz'
)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_field(kml_path):
    gdf = gpd.read_file(kml_path, driver='KML')
    geom = gdf.geometry.iloc[0]
    gdf_utm = gdf.to_crs(UTM_CRS)
    area_ha = gdf_utm.geometry.iloc[0].area / 10000.0
    bbox = geom.bounds  # (minx, miny, maxx, maxy)
    # Buffer bbox slightly to ensure full pixel coverage
    buf = 0.002  # ~200m
    bbox_buf = (bbox[0] - buf, bbox[1] - buf, bbox[2] + buf, bbox[3] + buf)
    return geom, area_ha, bbox, bbox_buf


# ============================================================================
# TOPOGRAPHY (Copernicus DEM 30m via MSPC)
# ============================================================================

def get_dem_array(geom, bbox_buf, catalog):
    log("  searching Copernicus DEM...")
    search = catalog.search(collections=['cop-dem-glo-30'], bbox=bbox_buf)
    items = list(search.items())
    log(f"  DEM tiles found: {len(items)}")
    if not items:
        raise RuntimeError("No DEM tiles found")

    # Stack and mosaic
    da = stackstac.stack(
        items,
        bounds_latlon=bbox_buf,
        epsg=4326,
        resolution=0.000277,  # ~30m at equator
        chunksize=2048,
    ).squeeze('band')

    if 'time' in da.dims:
        da = da.median(dim='time')

    da = da.compute()
    da = da.rio.write_crs('EPSG:4326')

    # Reproject to UTM for slope calculation in meters
    da_utm = da.rio.reproject(UTM_CRS, resampling=Resampling.bilinear)

    # Clip to actual polygon
    da_utm_clipped = da_utm.rio.clip(
        [mapping(geom)], crs='EPSG:4326', drop=True, all_touched=True,
    )

    return da_utm, da_utm_clipped


def compute_slope_aspect(dem_utm):
    """Compute slope (degrees) and aspect (degrees from N, clockwise) using np.gradient."""
    arr = dem_utm.values.astype('float32')
    arr = np.where(np.isnan(arr), np.nan, arr)
    # pixel size in meters
    res_x = float(abs(dem_utm.x[1] - dem_utm.x[0]))
    res_y = float(abs(dem_utm.y[1] - dem_utm.y[0]))
    # gradient: dy first axis (rows = y), dx second (cols = x)
    dy, dx = np.gradient(arr, res_y, res_x)
    slope_rad = np.arctan(np.sqrt(dx ** 2 + dy ** 2))
    slope_deg = np.degrees(slope_rad)
    # aspect: 0 = N, 90 = E (azimuth)
    aspect_rad = np.arctan2(-dx, dy)  # math conv; -dx for E positive
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.where(aspect_deg < 0, aspect_deg + 360, aspect_deg)

    slope_da = xr.DataArray(slope_deg, coords=dem_utm.coords, dims=dem_utm.dims)
    aspect_da = xr.DataArray(aspect_deg, coords=dem_utm.coords, dims=dem_utm.dims)
    slope_da = slope_da.rio.write_crs(dem_utm.rio.crs)
    aspect_da = aspect_da.rio.write_crs(dem_utm.rio.crs)
    return slope_da, aspect_da


def topo_stats(geom, dem_clipped, slope_da, aspect_da):
    log("  computing topography stats...")
    # Clip slope/aspect to polygon
    slope_clipped = slope_da.rio.clip([mapping(geom)], crs='EPSG:4326', drop=True, all_touched=True)
    aspect_clipped = aspect_da.rio.clip([mapping(geom)], crs='EPSG:4326', drop=True, all_touched=True)

    elev = dem_clipped.values
    slope = slope_clipped.values
    aspect = aspect_clipped.values

    elev_valid = elev[~np.isnan(elev)]
    slope_valid = slope[~np.isnan(slope)]
    aspect_valid = aspect[~np.isnan(aspect)]

    if len(elev_valid) == 0:
        log("  WARN: no elevation pixels in polygon")
        return {}

    # Slope buckets
    total = len(slope_valid)
    flat = float(np.sum(slope_valid < 5) / total * 100) if total else 0
    gentle = float(np.sum((slope_valid >= 5) & (slope_valid < 15)) / total * 100) if total else 0
    moderate = float(np.sum((slope_valid >= 15) & (slope_valid < 30)) / total * 100) if total else 0
    steep = float(np.sum(slope_valid >= 30) / total * 100) if total else 0

    # Aspect dominant: 8 sectors
    sector_names = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    sectors = ((aspect_valid + 22.5) // 45 % 8).astype(int)
    if len(sectors) > 0:
        counts = np.bincount(sectors, minlength=8)
        dominant = sector_names[int(np.argmax(counts))]
    else:
        dominant = 'N/A'

    return {
        'pixel_count': int(len(elev_valid)),
        'elev_mean_m': round(float(np.mean(elev_valid)), 1),
        'elev_min_m': round(float(np.min(elev_valid)), 1),
        'elev_max_m': round(float(np.max(elev_valid)), 1),
        'elev_std_m': round(float(np.std(elev_valid)), 2),
        'slope_mean_deg': round(float(np.mean(slope_valid)), 2),
        'slope_max_deg': round(float(np.max(slope_valid)), 2),
        'slope_std_deg': round(float(np.std(slope_valid)), 2),
        'dominant_aspect': dominant,
        'flat_lt5_pct': round(flat, 1),
        'gentle_5_15_pct': round(gentle, 1),
        'moderate_15_30_pct': round(moderate, 1),
        'steep_gte30_pct': round(steep, 1),
    }


# ============================================================================
# RAINFALL (CHIRPS monthly via direct HTTP)
# ============================================================================

def download_chirps_month(year, month):
    """Download one CHIRPS monthly GeoTIFF, return path to local file."""
    cache_path = CACHE_DIR / f'chirps_{year}_{month:02d}.tif'
    if cache_path.exists():
        return cache_path

    url = CHIRPS_URL_TEMPLATE.format(year=year, month=month)
    req = Request(url, headers={'User-Agent': 'pacifico-bambu-analysis/1.0'})
    with urlopen(req, timeout=120) as resp:
        gz_bytes = resp.read()
    raw = gzip.decompress(gz_bytes)
    cache_path.write_bytes(raw)
    return cache_path


def sample_chirps_at_polygon(tif_path, geom):
    """Return mean precipitation (mm) for the polygon."""
    with rasterio.open(tif_path) as src:
        out_img, out_transform = rio_mask(src, [mapping(geom)], crop=True, all_touched=True)
        arr = out_img[0].astype('float32')
        nodata = src.nodata if src.nodata is not None else -9999
        arr = np.where(arr <= nodata, np.nan, arr)
        valid = arr[~np.isnan(arr)]
        if len(valid) == 0:
            # Fallback: sample at centroid
            cx, cy = geom.centroid.x, geom.centroid.y
            for val in src.sample([(cx, cy)]):
                v = float(val[0])
                return v if v > nodata else 0.0
        return float(np.mean(valid))


def rainfall_stats(geom, name):
    log(f"  [{name}] rainfall from CHIRPS (this downloads ~120 small files, cached)...")
    annual = {}  # year -> total mm
    monthly_by_year = {}  # (year, month) -> mm

    for year in range(CHIRPS_START_YEAR, CHIRPS_END_YEAR + 1):
        annual[year] = 0.0
        for month in range(1, 13):
            try:
                tif = download_chirps_month(year, month)
                v = sample_chirps_at_polygon(tif, geom)
                monthly_by_year[(year, month)] = v
                annual[year] += v
            except Exception as e:
                log(f"    WARN: {year}-{month:02d} failed: {e}")
                monthly_by_year[(year, month)] = None
        log(f"    {year}: {annual[year]:.0f} mm")

    annual_vals = [v for v in annual.values() if v > 0]
    annual_mean = sum(annual_vals) / len(annual_vals) if annual_vals else 0
    annual_std = (sum((v - annual_mean) ** 2 for v in annual_vals) / len(annual_vals)) ** 0.5 if annual_vals else 0

    # Monthly climatology
    monthly_clim = {}
    for m in range(1, 13):
        vals = [monthly_by_year[(y, m)] for y in range(CHIRPS_START_YEAR, CHIRPS_END_YEAR + 1)
                if monthly_by_year.get((y, m)) is not None]
        monthly_clim[m] = sum(vals) / len(vals) if vals else 0

    wet_total = sum(v for m, v in monthly_clim.items() if m in WET_MONTHS)
    dry_total = sum(v for m, v in monthly_clim.items() if m in DRY_MONTHS)
    total = wet_total + dry_total

    return {
        'annual': sorted(annual.items()),
        'monthly_climatology': sorted(monthly_clim.items()),
        'monthly_by_year': monthly_by_year,
        'annual_mean_mm': round(annual_mean, 1),
        'annual_min_mm': round(min(annual_vals), 1) if annual_vals else 0,
        'annual_max_mm': round(max(annual_vals), 1) if annual_vals else 0,
        'annual_std_mm': round(annual_std, 1),
        'wet_season_mm': round(wet_total, 1),
        'dry_season_mm': round(dry_total, 1),
        'wet_share_pct': round(100 * wet_total / total, 1) if total > 0 else 0,
    }


# ============================================================================
# VEGETATION (Sentinel-2 L2A via MSPC)
# ============================================================================

def sentinel2_stats(geom, bbox_buf, catalog, name):
    log(f"  [{name}] searching Sentinel-2 L2A 2017-2026...")
    search = catalog.search(
        collections=['sentinel-2-l2a'],
        bbox=bbox_buf,
        datetime=f'{S2_START}/{S2_END}',
        query={'eo:cloud_cover': {'lt': 60}},
    )
    items = list(search.items())
    log(f"  found {len(items)} scenes")
    if len(items) == 0:
        return {}

    # Build stack with required bands at 10m
    bands = ['B04', 'B08', 'B11', 'SCL']
    da = stackstac.stack(
        items,
        assets=bands,
        bounds_latlon=bbox_buf,
        epsg=32614,  # UTM 14N
        resolution=10,
        chunksize=2048,
        dtype='float64',
        fill_value=np.nan,
        rescale=False,
    )

    log("  computing NDVI/NDMI per-scene (this may take a few minutes)...")
    scl = da.sel(band='SCL')
    # Keep classes: 4 vegetation, 5 not_veg, 6 water, 7 unclassified
    valid_mask = scl.isin([4, 5, 6, 7])

    b04 = da.sel(band='B04').where(valid_mask)
    b08 = da.sel(band='B08').where(valid_mask)
    b11 = da.sel(band='B11').where(valid_mask)

    ndvi = (b08 - b04) / (b08 + b04)
    ndmi = (b08 - b11) / (b08 + b11)

    # Add time month/year for grouping
    times = pd.DatetimeIndex(da.time.values)
    year_month_idx = times.strftime('%Y-%m')

    monthly_rows = []
    monthly_ndvi_means = {}
    monthly_ndmi_means = {}

    # Process by year to limit memory
    unique_yms = sorted(set(year_month_idx))
    log(f"  processing {len(unique_yms)} year-months...")

    for ym in unique_yms:
        year, month = int(ym[:4]), int(ym[5:7])
        mask_time = year_month_idx == ym
        n = int(mask_time.sum())
        if n == 0:
            continue

        ndvi_month = ndvi.isel(time=np.where(mask_time)[0]).median(dim='time', skipna=True)
        ndmi_month = ndmi.isel(time=np.where(mask_time)[0]).median(dim='time', skipna=True)

        try:
            ndvi_month = ndvi_month.compute()
            ndmi_month = ndmi_month.compute()
        except Exception as e:
            log(f"    {ym} compute failed: {e}")
            monthly_rows.append((year, month, None, None, n))
            continue

        # Clip to polygon
        ndvi_month = ndvi_month.rio.write_crs(32614)
        ndmi_month = ndmi_month.rio.write_crs(32614)
        try:
            ndvi_clip = ndvi_month.rio.clip([mapping(geom)], crs='EPSG:4326', drop=True, all_touched=True)
            ndmi_clip = ndmi_month.rio.clip([mapping(geom)], crs='EPSG:4326', drop=True, all_touched=True)
        except Exception:
            monthly_rows.append((year, month, None, None, n))
            continue

        nv = float(np.nanmean(ndvi_clip.values))
        nm = float(np.nanmean(ndmi_clip.values))
        nv = round(nv, 3) if not np.isnan(nv) else None
        nm = round(nm, 3) if not np.isnan(nm) else None
        monthly_rows.append((year, month, nv, nm, n))
        if nv is not None:
            monthly_ndvi_means[(year, month)] = nv
        if nm is not None:
            monthly_ndmi_means[(year, month)] = nm

    # Overall stats
    nv_all = [v for v in monthly_ndvi_means.values()]
    nm_all = [v for v in monthly_ndmi_means.values()]
    ndvi_mean = sum(nv_all) / len(nv_all) if nv_all else 0
    ndvi_std = (sum((v - ndvi_mean) ** 2 for v in nv_all) / len(nv_all)) ** 0.5 if nv_all else 0
    ndmi_mean = sum(nm_all) / len(nm_all) if nm_all else 0
    ndmi_std = (sum((v - ndmi_mean) ** 2 for v in nm_all) / len(nm_all)) ** 0.5 if nm_all else 0

    # Seasonal
    wet_nv = [v for (y, m), v in monthly_ndvi_means.items() if m in WET_MONTHS]
    dry_nv = [v for (y, m), v in monthly_ndvi_means.items() if m in DRY_MONTHS]
    wet_nm = [v for (y, m), v in monthly_ndmi_means.items() if m in WET_MONTHS]
    dry_nm = [v for (y, m), v in monthly_ndmi_means.items() if m in DRY_MONTHS]

    # Trend (slope per year of yearly mean)
    yearly_ndvi = {}
    yearly_ndmi = {}
    for (y, m), v in monthly_ndvi_means.items():
        yearly_ndvi.setdefault(y, []).append(v)
    for (y, m), v in monthly_ndmi_means.items():
        yearly_ndmi.setdefault(y, []).append(v)
    nv_yearly = sorted((y, sum(vals) / len(vals)) for y, vals in yearly_ndvi.items())
    nm_yearly = sorted((y, sum(vals) / len(vals)) for y, vals in yearly_ndmi.items())

    def slope_per_year(pairs):
        if len(pairs) < 2:
            return None
        xs = np.array([p[0] for p in pairs], dtype=float)
        ys = np.array([p[1] for p in pairs], dtype=float)
        n = len(xs)
        denom = (n * (xs ** 2).sum() - xs.sum() ** 2)
        if denom == 0:
            return None
        slope = (n * (xs * ys).sum() - xs.sum() * ys.sum()) / denom
        return float(slope)

    return {
        'scene_count': len(items),
        'monthly_rows': monthly_rows,
        'ndvi_mean': round(ndvi_mean, 3),
        'ndvi_std': round(ndvi_std, 3),
        'ndmi_mean': round(ndmi_mean, 3),
        'ndmi_std': round(ndmi_std, 3),
        'ndvi_wet_mean': round(sum(wet_nv) / len(wet_nv), 3) if wet_nv else 0,
        'ndvi_dry_mean': round(sum(dry_nv) / len(dry_nv), 3) if dry_nv else 0,
        'ndmi_wet_mean': round(sum(wet_nm) / len(wet_nm), 3) if wet_nm else 0,
        'ndmi_dry_mean': round(sum(dry_nm) / len(dry_nm), 3) if dry_nm else 0,
        'ndvi_trend_per_year': round(slope_per_year(nv_yearly), 4) if slope_per_year(nv_yearly) is not None else None,
        'ndmi_trend_per_year': round(slope_per_year(nm_yearly), 4) if slope_per_year(nm_yearly) is not None else None,
    }


# ============================================================================
# OUTPUT WRITERS
# ============================================================================

def write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    log(f"  wrote {path.name}")


def write_markdown(summaries):
    lines = []
    lines.append('# סיכום נתוני שטח — Pacifico Bambu\n')
    lines.append(f'נוצר ב-{datetime.now().strftime("%Y-%m-%d %H:%M")} באמצעות Microsoft Planetary Computer + CHIRPS.\n')
    lines.append('## מקורות נתונים')
    lines.append('- **טופוגרפיה**: Copernicus DEM 30m (Microsoft Planetary Computer)')
    lines.append('- **משקעים**: CHIRPS 2.0 Monthly 5km (UCSB CHC), 2016–2025')
    lines.append('- **צמחייה**: Sentinel-2 L2A 10m (Microsoft Planetary Computer), 2017–2026, cloud<60%, SCL masked\n')

    lines.append('## טבלת השוואה — שני השדות\n')
    lines.append('| מדד | שדה 1 (Guadua 6Y) | שדה 2 |')
    lines.append('|------|-------------------|--------|')

    def row(label, key, fmt='{}'):
        v1 = summaries[0].get(key, 'N/A')
        v2 = summaries[1].get(key, 'N/A')
        s1 = fmt.format(v1) if v1 not in ('N/A', None) else 'N/A'
        s2 = fmt.format(v2) if v2 not in ('N/A', None) else 'N/A'
        return f'| {label} | {s1} | {s2} |'

    lines.append(row('שטח (הקטר)', 'area_ha', '{:.3f}'))
    lines.append(row('שטח (מ"ר)', 'area_m2', '{:,.0f}'))
    lines.append(row('פיקסלי DEM בפוליגון', 'pixel_count'))
    lines.append(row('גובה ממוצע (מ\')', 'elev_mean_m'))
    lines.append(row('גובה min (מ\')', 'elev_min_m'))
    lines.append(row('גובה max (מ\')', 'elev_max_m'))
    lines.append(row('גובה std (מ\')', 'elev_std_m'))
    lines.append(row('שיפוע ממוצע (°)', 'slope_mean_deg'))
    lines.append(row('שיפוע מקסימלי (°)', 'slope_max_deg'))
    lines.append(row('שיפוע std (°)', 'slope_std_deg'))
    lines.append(row('כיוון מדרון דומיננטי', 'dominant_aspect'))
    lines.append(row('שטוח <5° (%)', 'flat_lt5_pct'))
    lines.append(row('עדין 5-15° (%)', 'gentle_5_15_pct'))
    lines.append(row('בינוני 15-30° (%)', 'moderate_15_30_pct'))
    lines.append(row('תלול ≥30° (%)', 'steep_gte30_pct'))
    lines.append(row('משקעים שנתיים ממוצע (מ"מ)', 'annual_mean_mm'))
    lines.append(row('משקעים שנתיים std', 'annual_std_mm'))
    lines.append(row('שנה יבשה ביותר (מ"מ)', 'annual_min_mm'))
    lines.append(row('שנה גשומה ביותר (מ"מ)', 'annual_max_mm'))
    lines.append(row('עונת גשם May-Oct (מ"מ)', 'wet_season_mm'))
    lines.append(row('עונת יבש Nov-Apr (מ"מ)', 'dry_season_mm'))
    lines.append(row('חלק עונת גשם (%)', 'wet_share_pct'))
    lines.append(row('Sentinel-2 scenes (סה"כ)', 'scene_count'))
    lines.append(row('NDVI ממוצע', 'ndvi_mean'))
    lines.append(row('NDVI עונת גשם', 'ndvi_wet_mean'))
    lines.append(row('NDVI עונת יבש', 'ndvi_dry_mean'))
    lines.append(row('NDMI ממוצע', 'ndmi_mean'))
    lines.append(row('NDMI עונת גשם', 'ndmi_wet_mean'))
    lines.append(row('NDMI עונת יבש', 'ndmi_dry_mean'))
    lines.append(row('מגמת NDVI לשנה', 'ndvi_trend_per_year'))
    lines.append(row('מגמת NDMI לשנה', 'ndmi_trend_per_year'))

    lines.append('\n## פרשנות מהירה\n')
    for s in summaries:
        lines.append(f'### {s["display_name"]}')
        elev = s.get('elev_mean_m', 0)
        slope = s.get('slope_mean_deg', 0)
        ndvi = s.get('ndvi_mean', 0)
        ndmi = s.get('ndmi_mean', 0)
        rain = s.get('annual_mean_mm', 0)
        lines.append(f'- **שטח**: {s["area_ha"]:.3f} ha ({s["area_m2"]:,.0f} מ"ר)')
        lines.append(f'- **גובה**: ממוצע {elev}מ\', טווח {s.get("elev_min_m")}–{s.get("elev_max_m")}מ\'')
        lines.append(f'- **שיפוע**: ממוצע {slope}° (מקס {s.get("slope_max_deg")}°), כיוון דומיננטי {s.get("dominant_aspect")}')
        slope_assess = (
            'שטח שטוח — אידאלי לחקלאות' if slope < 5
            else 'שיפוע מתון — חקלאות ללא מגבלות' if slope < 15
            else 'שיפוע משמעותי — שקול טראסות / שמירת קרקע' if slope < 25
            else 'תלול — דורש הנדסה מיוחדת'
        )
        lines.append(f'  - הערכה: {slope_assess}')
        lines.append(f'- **משקעים**: {rain} מ"מ/שנה (טווח {s.get("annual_min_mm")}–{s.get("annual_max_mm")})')
        lines.append(f'  - {s.get("wet_share_pct")}% מהמשקעים בעונת מאי–אוקטובר')
        lines.append(f'- **NDVI**: {ndvi} (יבש: {s.get("ndvi_dry_mean")}, גשום: {s.get("ndvi_wet_mean")})')
        ndvi_assess = (
            'צמחייה דלה' if ndvi < 0.3
            else 'צמחייה בינונית' if ndvi < 0.5
            else 'צמחייה בריאה' if ndvi < 0.7
            else 'צמחייה צפופה ובריאה — אופייני ל-Guadua בוגר'
        )
        lines.append(f'  - הערכה: {ndvi_assess}')
        lines.append(f'- **NDMI**: {ndmi} (יבש: {s.get("ndmi_dry_mean")}, גשום: {s.get("ndmi_wet_mean")})')
        ndmi_assess = (
            'לחות נמוכה — סטרס מים' if ndmi < 0.0
            else 'לחות בינונית' if ndmi < 0.2
            else 'לחות גבוהה' if ndmi < 0.4
            else 'לחות גבוהה מאוד — צמחייה רוויית מים'
        )
        lines.append(f'  - הערכה: {ndmi_assess}')
        trend = s.get('ndvi_trend_per_year')
        if trend is not None:
            trend_dir = 'עלייה' if trend > 0.005 else 'יציבות' if trend > -0.005 else 'ירידה'
            lines.append(f'- **מגמת NDVI**: {trend:+.4f}/שנה ({trend_dir})')
        lines.append('')

    lines.append('## מגבלות\n')
    lines.append('- **CHIRPS 5km** > גודל השדות (100–300m): שני השדות מקבלים כמעט אותו ערך משקעים. תקף ל-regional climate, לא לוריאציה מקומית.')
    lines.append('- **Copernicus DEM 30m**: שדה ראשון ~5–10 פיקסלים, שדה שני ~30–50. שיפוע משוערך עם np.gradient — מדויק לטופוגרפיה כללית.')
    lines.append('- **Sentinel-2**: לאחר cloud masking, חלק מהחודשים בעונת גשם עלולים להיות חסרים. עמודת "scenes" מציגה כמה תמונות נכנסו לכל חודש.')
    lines.append('- כל הסטטיסטיקות הן ממוצעי שטח. לוריאציה נקודתית נדרשת תיעוד שטח או מערכת אגרו-נומית.')

    out_path = OUT_DIR / 'field_summary.md'
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    log(f"  wrote {out_path.name}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    log("Initializing STAC catalog (Microsoft Planetary Computer)...")
    catalog = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)

    summaries = []
    per_field_data = {}

    for key, kml_path, display in FIELDS:
        log(f"\n=== {display} ({key}) ===")
        geom, area_ha, bbox, bbox_buf = load_field(kml_path)
        log(f"  area: {area_ha:.4f} ha, bbox: {bbox}")

        # Topography
        dem_utm, dem_clip = get_dem_array(geom, bbox_buf, catalog)
        slope_da, aspect_da = compute_slope_aspect(dem_utm)
        topo = topo_stats(geom, dem_clip, slope_da, aspect_da)

        # Rainfall
        rain = rainfall_stats(geom, key)

        # Vegetation
        veg = sentinel2_stats(geom, bbox_buf, catalog, key)

        summary = {
            'field_key': key,
            'display_name': display,
            'area_ha': round(area_ha, 4),
            'area_m2': round(area_ha * 10000, 1),
            **topo,
            'annual_mean_mm': rain.get('annual_mean_mm'),
            'annual_min_mm': rain.get('annual_min_mm'),
            'annual_max_mm': rain.get('annual_max_mm'),
            'annual_std_mm': rain.get('annual_std_mm'),
            'wet_season_mm': rain.get('wet_season_mm'),
            'dry_season_mm': rain.get('dry_season_mm'),
            'wet_share_pct': rain.get('wet_share_pct'),
            'scene_count': veg.get('scene_count', 0),
            'ndvi_mean': veg.get('ndvi_mean'),
            'ndvi_std': veg.get('ndvi_std'),
            'ndmi_mean': veg.get('ndmi_mean'),
            'ndmi_std': veg.get('ndmi_std'),
            'ndvi_wet_mean': veg.get('ndvi_wet_mean'),
            'ndvi_dry_mean': veg.get('ndvi_dry_mean'),
            'ndmi_wet_mean': veg.get('ndmi_wet_mean'),
            'ndmi_dry_mean': veg.get('ndmi_dry_mean'),
            'ndvi_trend_per_year': veg.get('ndvi_trend_per_year'),
            'ndmi_trend_per_year': veg.get('ndmi_trend_per_year'),
        }
        summaries.append(summary)
        per_field_data[key] = {'rain': rain, 'veg': veg}

    # Write outputs
    log("\nWriting outputs...")
    summary_csv = OUT_DIR / 'field_summary.csv'
    keys = list(summaries[0].keys())
    with open(summary_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for s in summaries:
            w.writerow(s)
    log(f"  wrote {summary_csv.name}")

    # Monthly rainfall climatology
    rain1 = dict(per_field_data['first_field']['rain']['monthly_climatology'])
    rain2 = dict(per_field_data['second_field']['rain']['monthly_climatology'])
    rows = [[m, round(rain1[m], 1), round(rain2[m], 1)] for m in range(1, 13)]
    write_csv(OUT_DIR / 'monthly_rainfall_climatology.csv',
              ['month', 'first_field_mm', 'second_field_mm'], rows)

    # Annual rainfall
    ann1 = dict(per_field_data['first_field']['rain']['annual'])
    ann2 = dict(per_field_data['second_field']['rain']['annual'])
    rows = [[y, round(ann1[y], 1), round(ann2[y], 1)] for y in sorted(ann1)]
    write_csv(OUT_DIR / 'annual_rainfall_2016-2025.csv',
              ['year', 'first_field_mm', 'second_field_mm'], rows)

    # NDVI/NDMI monthly
    m1 = {(y, m): (nv, nm, n) for y, m, nv, nm, n in per_field_data['first_field']['veg'].get('monthly_rows', [])}
    m2 = {(y, m): (nv, nm, n) for y, m, nv, nm, n in per_field_data['second_field']['veg'].get('monthly_rows', [])}
    all_ym = sorted(set(m1) | set(m2))
    ndvi_rows = []
    ndmi_rows = []
    for ym in all_ym:
        a = m1.get(ym, (None, None, 0))
        b = m2.get(ym, (None, None, 0))
        ndvi_rows.append([ym[0], ym[1], a[0], b[0], a[2], b[2]])
        ndmi_rows.append([ym[0], ym[1], a[1], b[1], a[2], b[2]])
    write_csv(OUT_DIR / 'ndvi_monthly_2017-2026.csv',
              ['year', 'month', 'first_field_NDVI', 'second_field_NDVI', 'first_field_scenes', 'second_field_scenes'],
              ndvi_rows)
    write_csv(OUT_DIR / 'ndmi_monthly_2017-2026.csv',
              ['year', 'month', 'first_field_NDMI', 'second_field_NDMI', 'first_field_scenes', 'second_field_scenes'],
              ndmi_rows)

    # Markdown summary
    write_markdown(summaries)

    log("\nDONE. Outputs in: " + str(OUT_DIR))


if __name__ == '__main__':
    main()
