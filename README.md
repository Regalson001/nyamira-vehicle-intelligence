<div align="center">

# 🚦 Nyamira Town Vehicle Entry, Exit & Route Intelligence System

**Real-Time Gate Telemetry, Kenyan ANPR/Manual Registration Validation, Automated Dwell Pairing & Geospatial Corridor Analytics for Nyamira County**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?style=for-the-badge)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6%2B-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Leaflet](https://img.shields.io/badge/Leaflet.js-1.9.4-199900?style=for-the-badge&logo=leaflet&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-64748b?style=for-the-badge)

</div>

---

## 📑 Table of Contents

1. [Executive Overview](#-executive-overview)
2. [Operational Challenges Solved](#-operational-challenges-solved)
3. [Key System Capabilities](#-key-system-capabilities)
4. [System Architecture & Data Pipeline](#-system-architecture--data-pipeline)
5. [Monitored Nyamira Corridors & Checkpoints](#-monitored-nyamira-corridors--checkpoints)
6. [Kenyan Registration Plate Validation Engine](#-kenyan-registration-plate-validation-engine)
7. [Automated ENTRY → EXIT Pairing & Anomaly Rules](#-automated-entry--exit-pairing--anomaly-rules)
8. [REST API Reference](#-rest-api-reference)
9. [Project Directory Structure](#-project-directory-structure)
10. [Local Setup & Quickstart](#-local-setup--quickstart)
11. [Production Deployment (PostgreSQL & Docker)](#-production-deployment-postgresql--docker)
12. [Roadmap](#-roadmap)
13. [Author](#-author)

---

## 🎯 Executive Overview

**Nyamira Town Vehicle Entry, Exit & Route Intelligence System** is a regional municipal traffic and security intelligence platform engineered for **Nyamira Town, Nyamira County, Kenya (`-0.5633, 34.9358`)**. 

Designed specifically for low-to-moderate traffic regional towns, the platform replaces paper checkpoint logbooks with a unified digital command center that tracks every inbound (`ENTRY`) and outbound (`EXIT`) vehicle across major arterial roads, calculates exact town dwell durations, maps live corridor utilization on OpenStreetMap, and flags overstays or irregular transit patterns in real time.

---

## 🧩 Operational Challenges Solved

| Municipal / Security Challenge | Platform Solution |
| :--- | :--- |
| **Unverified Town Occupancy** | Tracks every unpaired `ENTRY` event in real time to maintain an exact count and registry of vehicles currently inside Nyamira town limits. |
| **Manual Logbook Errors & Invalid Plates** | Enforces strict regex normalization and validation for Kenyan civilian (`KDA 123A`), government (`GK 418C`), and diplomatic (`CD 102A`) registrations. |
| **Unmonitored Long-Dwell / Overstay Vehicles** | Automatically pairs `ENTRY` and `EXIT` events by registration number, calculates dwell minutes, and flags vehicles remaining inside town beyond `240 minutes` (4 hours). |
| **Blind Spots Across Arterial Approaches** | Maps live traffic volume and movement pins across **Kisii–Nyamira Road**, **Sotik–Nyamira Road**, **Kebirigo–Ikonge Road**, and **Nyamira Town Center / Hospital Junction**. |
| **Late-Night & Repeat-Pass Security Risks** | Automatically flags off-peak transit (`23:00 – 04:30`) and high-frequency repeat passes (`>= 5` gate events within 6 hours). |

---

## ✨ Key System Capabilities

* **Real-Time Gate Event Ingestion (`ANPR` & `MANUAL`):** Supports both automated camera webhook payloads and rapid manual operator logging via an integrated Quick-Log modal.
* **Automatic `ENTRY` → `EXIT` Dwell Pairing:** Links outbound departures to the vehicle's most recent inbound record, computing exact town dwell time in minutes and updating live town occupancy counts.
* **Interactive Leaflet.js Geospatial Map:** Centered on Nyamira Town (`[-0.5633, 34.9358]`) with OpenStreetMap tiles, corridor polylines, checkpoint markers, and color-coded vehicle movement pins (`Green = ENTRY`, `Amber = EXIT`).
* **Executive KPI & Triage Dashboard:** Displays live counters for **Entries Today**, **Exits Today**, **Currently Inside Town**, **Average Town Dwell Time**, and **Anomaly & Overstay Alerts**.
* **Multi-Faceted Search & Filtering:** Filter live movement logs instantly by registration plate, transit corridor, direction (`ENTRY` / `EXIT`), and vehicle classification (`Matatu/PSV`, `Cargo/Agro-Freight`, `Private`, `Delivery Van`, `Government`).
* **Built-In Traffic Burst Simulator:** One-click simulation endpoint (`POST /api/simulate`) generating realistic Nyamira corridor entries and paired exits for immediate demonstration and load verification.

---

## 🏗️ System Architecture & Data Pipeline

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              1. CHECKPOINT CAPTURE LAYER                                 │
│   • ANPR Camera Webhooks (JSON)      • Gate Operator Manual UI      • Traffic Simulator  │
└────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                             │ HTTP POST /api/events
                                             ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                          2. FASTAPI INTELLIGENCE & PAIRING ENGINE                        │
│   • Pydantic Plate Normalization     • ENTRY -> EXIT Session Matcher                     │
│   • Geospatial Coordinate Resolver   • Rule-Based Anomaly Detector (Overstay/Night/Loop) │
└────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                             │ SQLAlchemy ORM
                                             ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                            3. PERSISTENCE LAYER (SQLite / PostgreSQL)                    │
│   • Indexed `vehicle_movements` table with live `is_currently_inside` state flags        │
└────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                             │ JSON REST API (5s Auto-Sync)
                                             ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                        4. EXECUTIVE OPERATIONS DASHBOARD (Leaflet + ES6)                 │
│   • Live Nyamira Corridor Map        • KPI Summary Cards        • Triage & Dwell Table   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
