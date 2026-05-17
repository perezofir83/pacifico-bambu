# Field Data Extraction — Pacifico Bambu

חילוץ נתוני שטח לשני שדות Guadua באוקסקה, מקסיקו, באמצעות Google Earth Engine.

## מקורות הנתונים

| מקור | רזולוציה | תקופה | משמש ל | פלטפורמה |
|------|----------|--------|---------|----------|
| Copernicus DEM GLO-30 | 30m | סטטי | גובה, שיפוע, aspect | MS Planetary Computer |
| CHIRPS 2.0 Monthly | 5km | 2016–2025 | משקעים + climatology | UCSB CHC (HTTP) |
| Sentinel-2 L2A | 10m | 2017–2026 | NDVI, NDMI | MS Planetary Computer |

חינמי לחלוטין, אין צורך ב-API key או חשבון.

## הרצה

```bash
pip3 install -r requirements.txt
python3 extract_field_data.py
```

הרצה ראשונה: ~10–25 דקות (תלוי בקצב CHIRPS download — 120 קבצים נחבאים ב-`.cache/`).
הרצות חוזרות: ~3–5 דקות (CHIRPS נטענים מהקאש).

## Outputs (תיקיית `outputs/`)

- `field_summary.csv` — שורה אחת לכל שדה: שטח, גובה, שיפוע, NDVI/NDMI ממוצעים, משקעים שנתיים ממוצעים
- `field_summary.md` — סיכום בעברית עם הסברים
- `monthly_rainfall_climatology.csv` — ממוצע מ"מ לחודש (Jan-Dec, מ-2016-2025)
- `annual_rainfall_2016-2025.csv` — סה"כ שנתי
- `ndvi_monthly_2017-2026.csv` — NDVI חודשי לאורך השנים
- `ndmi_monthly_2017-2026.csv` — NDMI חודשי לאורך השנים

## מגבלות

- **CHIRPS 5km > גודל השדות (100–300m)**: שני השדות יקבלו כמעט אותו ערך משקעים. זה rainfall regional תקף, לא נקודתי.
- **SRTM 30m**: שדה ראשון מקבל ~5–10 פיקסלים, שדה שני ~30–50. מספיק לטופוגרפיה כללית.
- **Sentinel-2 cloud masking**: עונת הגשמים באוקסקה — תמונות נקיות מועטות; הסקריפט מציג את מספר התמונות שנכנסו לחישוב.
