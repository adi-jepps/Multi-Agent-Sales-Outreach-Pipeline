import numpy as np
import pandas as pd 
import glob

csv_file = glob.glob("C:/Users/AJeppu/Sales-internal/data/final-market-leads.csv")

raw_dfs = [pd.read_csv(f) for f in csv_file]
dfs =  pd.concat(raw_dfs, ignore_index=True)

research_fields = [
    "First Name", "Last Name", "Title", "Seniority", "Departments",
    "Company Name", "Email", "Email Status", "Email Confidence",
    "Person Linkedin Url", "Website", "Company Linkedin Url",
    "City", "State", "Country",
    "Company City", "Company State", "Company Country",
    "# Employees", "Industry", "Keywords",
]

filtered_dfs = dfs[research_fields].copy()
filtered_dfs.to_csv("relevant-columns.csv", index=False)


