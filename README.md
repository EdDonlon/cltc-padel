# Charleville LTC Padel Box League Sep-Nov 2026

A simple Streamlit app showing live results & leag tables for a padel box league.


### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Create `.streamlit/secrets.toml` with the Google Sheets identifiers:

   ```toml
   [sheet_ids]
   spreadsheet_id = "your-spreadsheet-id"
   emerald_gid = "your-emerald-sheet-gid"
   shamrock_gid = "your-shamrock-sheet-gid"
   ```

   The `.streamlit/secrets.toml` file is ignored by Git. When deploying with
   Streamlit Community Cloud, add the same TOML configuration in the app's
   **Settings > Secrets**.

3. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```
