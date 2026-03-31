# JOBSEARCH Automation & Trackers

A centralized, automated Python-based repository designed to host job application assets, trackers, and intelligent automation scripts to streamline job search activities.

## 🚀 Overview

This repository has evolved from an initialization placeholder into a fully functioning Python environment powered by advanced automation tools and LLMs.

**Key Features:**
- **Automated Web Interactions:** Powered by Playwright and `playwright-stealth` for navigating careers portals.
- **LLM Integration:** Utilizes `groq` for intelligent matching and evaluation of job descriptions against your profile.
- **Application Dashboard:** A local Flask dashboard to track jobs and applications.
- **Configurable Profiles:** Centralized user configuration via YAML.

## 📂 Key Components

- `config/user_profile.yaml`: Your master configuration file containing targeted titles, skills, minimum salary, and blocked companies.
- `run_dashboard.sh`: Shell script to quickly boot up the local Flask tracking dashboard.
- `pyproject.toml`: Manages dependencies such as Playwright, Groq, SQLAlchemy, and Flask.
- `src/`: Core Python modules housing the automation logic and DB models.

## 🛠 Setup & Execution

1. **Install Dependencies:**
   Ensure Python 3.14+ is installed. Use your preferred package manager (like `uv` or `pip`) to install dependencies outlined in `pyproject.toml`.

2. **Configure Your Profile:**
   Edit `config/user_profile.yaml` to match your background and job search targets (e.g. Senior QA Engineer, API testing, etc.).

3. **Run the Dashboard:**
   Execute the dashboard locally to monitor your application progress:
   ```bash
   ./run_dashboard.sh
   ```
