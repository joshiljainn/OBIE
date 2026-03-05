# **Product Requirements Document (PRD): OSINT Buyer Intent Engine**  
## **1. Product Overview**  
A lightweight, open-source pipeline that automates Open Source Intelligence (OSINT) to find, verify, and enrich international B2B buyer leads for exporters. It replaces expensive databases (like Zauba/Volza) by scraping the open web, using AI to verify intent, and validating contact details.  
## **2. Target Audience & Problem**  
* **Audience:** Exporters looking for international distributors, wholesalers, and direct buyers.  
* **Problem:** Existing databases are expensive, outdated, or filled with competitors and dead companies. Manual Google searching is incredibly time-consuming.  
* **Solution:** An automated script that turns a search query (e.g., "distributor", "target country", "product") into a verified, clean CSV of decision-makers.  
## **3. Core Features & Tech Stack**  
* **Feature 1: The Crawler.** Executes advanced Google Dorks via headless browser to find target domains. *(Tech: Python, Playwright)*  
* **Feature 2: The AI Verifier.** Scrapes site content and uses an LLM to categorize the company (Buyer vs. Competitor) and verify relevance. *(Tech: BeautifulSoup, Groq API for Llama 3 - for speed and generous free tier)*  
* **Feature 3: The Validator.** Hunts for contact details and runs an SMTP ping to verify if the email address actually exists. *(Tech: Python smtplib, Regex, dnspython)*  
## **4. Non-Goals (Out of Scope for v1)**  
* No frontend GUI or web dashboard (CLI/Script-based for now).  
* No built-in cold email sending (outputs to CSV for import into dedicated tools).  
* No database architecture (files stored locally as CSV/JSON).  
