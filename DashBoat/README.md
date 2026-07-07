# DashBoat - Setup Instructions

## Installation Steps

### Step 1: Install Python Dependencies

Open terminal/command prompt and run:

```bash
pip install -r requirements.txt
```

This will install all required Python packages including:
- pandas, numpy (data processing)
- matplotlib, seaborn, plotly (visualizations)
- reportlab, PyPDF2 (PDF generation)
- openai (AI integration)
- psycopg2 (database)

### Step 2: Install Odoo Module

1. Copy the `DashBoat` folder to your Odoo addons directory
   - Example: `C:\Program Files\Odoo 18.0\server\odoo\addons\DashBoat`

2. Restart your Odoo server

3. Update Apps List:
   - Go to Odoo → Apps menu
   - Click "Update Apps List" button

4. Install Module:
   - Search for "DashBoat" in Apps
   - Click "Install" button

### Step 3: Configure OpenAI API Key

1. Navigate to **DashBoat → Registration** in Odoo menu
2. Enter your OpenAI API key in the registration form
3. Click "Save"

**Note**: You need a valid OpenAI API key for AI-powered features to work.

### Step 4: Verify Installation

1. Go to **DashBoat → Sales Dashboard**
2. You should see the dashboard with charts and metrics
3. Try clicking "Download Report" to test PDF generation
4. Try clicking "AI Analysis" to test Insight generation
5. Try clicking "chat Toggle" to test Chat functionality

## Requirements

- Odoo 18.0 or higher
- Python 3.8 or higher
- PostgreSQL database
- OpenAI API key (for AI features)

## Troubleshooting

**If module doesn't appear in Apps:**
- Check that folder is in correct addons directory
- Restart Odoo server
- Check file permissions

**If dependencies fail to install:**
- Make sure you're using correct Python version
- Try: `pip install --upgrade pip` first
- Install dependencies one by one if needed

**If OpenAI features don't work:**
- Verify API key is correct
- Check API key has sufficient credits
- Check internet connection

---

**Setup Complete!** You can now use DashBoat dashboards and AI chatbot features.

## PDF Cover Page & Company Name

By default, the PDF report cover page displays the report title (e.g., "Sales Dashboard Report") and the selected date range below it. The descriptive subtitle (e.g., 'Performance Report') has been removed to keep the cover clean; only the report title and date are shown.
as footer text. To override the company name and footer in the PDF, set a system parameter
`dashboat.report_company_name` in Odoo (Settings > Technical > Parameters > System Parameters) to your desired
company string (e.g., 'Sufalamtech'). If not set, the module falls back to the Odoo company name.

The cover and footer styling are implemented in the module's PDF generators (ReportLab). If you want to adjust
styles (colors, fonts, or line thickness), modify `models/predictive_engine.py` where the PDF generation occurs.
