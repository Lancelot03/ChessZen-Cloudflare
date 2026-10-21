# ChessZen Classes - Product Requirements Document

## Original Problem Statement
Create a premium, modern, mobile-first, fully responsive website for a chess coaching brand named "ChessZen Classes" run by Coach Vivek Singh. The goal is to generate inquiries, collect/display testimonials, and encourage demo class bookings.

## Core Sections
Hero, About Coach, Why ChessZen, Programs, Benefits, Training Approach, Achievements, Testimonials, Enquiry Form, Contact, FAQ, Meet Our Internal Team (Vaibhav & Ramya), Footer

## Admin Panel
- httpOnly cookie-based JWT authentication (secure, no localStorage)
- Testimonial moderation (approve/reject/delete)
- View enquiries and demo bookings
- Booking status management (confirm/cancel/complete)
- Quick-stats dashboard overview

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn UI
- Backend: FastAPI, PyMongo, MongoDB
- Email: Resend API
- Auth: JWT via httpOnly cookies

## Design Theme
- Premium Light/Amber theme with wooden chessboard backgrounds
- Chess pieces must show correct starting position (White bottom, ranks 1 & 2)
- Admin pages: Dark glass-morphism over chessboard background

## What's Been Implemented (All DONE)
- Full frontend with all sections
- Full backend with all API endpoints
- Admin panel with login + dashboard (cookie-based auth)
- Admin dashboard quick-stats overview
- Admin Analytics Dashboard with visitor tracking (Apr 21, 2026):
  - Automatic visitor tracking via cookies (unique per device per day)
  - KPI cards: Today, This Week, This Month, All Time visitors
  - Daily traffic trend area chart (7/14/30/60 day ranges)
  - Weekly comparison bar chart
  - Peak traffic hours bar chart
  - Device breakdown donut chart (Mobile/Desktop)
  - Top pages visited with progress bars
  - AI insights banner (traffic change %, peak hours)
  - CSV export functionality
  - Date range filters
- Student Management Portal Phase 1 (May 26, 2026):
  - Sidebar navigation layout (Dashboard, Students, Batches + disabled upcoming tabs)
  - Batch Management: CRUD batches with schedule (days + time), max capacity, holiday management
  - Student Profiles: Full CRUD with photo upload, searchable/filterable table, age group, chess level, country code phone, parent name, fee per block, status toggle
  - Dashboard: KPI cards (total/active/inactive students, batches), batch capacity chart, chess level distribution
- Student Management Portal Phase 2 & 3 (May 26, 2026):
  - Attendance: Date picker + batch filter, mark Present/Late/Absent, bulk "All Present/Absent", previously-marked indicator, save attendance
  - Fee Tracking: Monthly/total revenue cards, pending fees calculation, record payments (amount, date, method, sessions), payment history per student, "Send Fee Reminder" with pre-formatted WhatsApp message + UPI details
  - Performance: Add test entries (name, date, score 0-100, remarks), file attachments (up to 3 per test), score progression line chart, score summary stats, batch leaderboard by test name
  - Communications: Broadcast message to batch (generates WhatsApp links per student), upcoming birthdays (7-day window) with quick-send, progress report generation (attendance + tests), communication history log
- Bulk Upload & Individual Reminders (Jun 11, 2026):
  - Excel template download with headers, data validations (dropdowns), instructions sheet
  - Bulk upload students from .xlsx with validation (age group, batch name matching), error reporting
  - All Students fee actions section with individual View/Pay/Remind buttons per student
  - Search filter in fee actions list
- Student Detail Page, Report Cards, Fee Reminder Cards, Tournaments (Aug 23, 2026):
  - Student Detail Page: Monthly attendance graph (conducted vs attended bar chart), test score progression line chart, 4 KPI cards, back navigation
  - Shareable Fee Reminder Card: Attractive card with mini attendance graph, fee summary, UPI payment details, download as image + WhatsApp share
  - Auto-generated Report Card: Full performance report (attendance %, monthly breakdown, test scores, stats), downloadable as PNG image
  - Tournament/Test Scheduling: Create/edit/delete tournaments with batch assignment, inline score entry grid per student, scores auto-create test entries
  - Sidebar updated with Tournaments tab
- Resend email notifications
- Demo class booking with calendar modal
- Team section (Vaibhav & Ramya)
- Premium chessboard backgrounds on admin pages
- Testimonial modal scroll fix
- SEO metadata and analytics
- WhatsApp/Emergent badge overlap fix
- Code review fixes (Apr 14, 2026):
  - Security: Migrated from localStorage to httpOnly cookies for JWT auth
  - React Hooks: Added useCallback with proper dependency arrays
  - Component splitting: AdminPage -> AdminStats, AdminBookings, AdminTestimonials, AdminEnquiries
  - Array index keys replaced with meaningful keys
  - Console statements removed
  - Nested ternaries replaced with lookup objects
  - Accessibility: Added DialogDescription to all modals
  - Code review fixes Round 2 (Apr 20, 2026):
    - Replaced all array-index keys with stable identifiers across 13 components
    - Extracted inline toastOptions to module constant in App.js
    - Split AdminPage heavy useEffect into 2 focused effects
    - Removed hardcoded credentials from test file (uses env vars)
    - Fixed assert comparison in tests
    - Removed console.warn from craco.config.js

## Architecture
```
/app/
├── backend/
│   ├── server.py
│   ├── tests/test_auth_cookies.py
│   ├── .env
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.js
    │   ├── components/
    │   │   ├── admin/
    │   │   │   ├── AdminStats.jsx
    │   │   │   ├── AdminBookings.jsx
    │   │   │   ├── AdminTestimonials.jsx
    │   │   │   └── AdminEnquiries.jsx
    │   │   ├── Hero.jsx, AboutCoach.jsx, Team.jsx, etc.
    │   │   ├── Testimonials.jsx
    │   │   ├── BookingModal.jsx
    │   │   └── WhatsAppButton.jsx
    │   └── pages/
    │       ├── HomePage.jsx
    │       ├── AdminPage.jsx
    │       └── AdminLogin.jsx
    └── public/index.html
```

## Key API Endpoints
- POST /api/auth/login (Sets httpOnly cookies, no token in response body)
- POST /api/auth/logout (Clears cookies)
- GET /api/auth/me (Reads cookie for auth)
- GET /api/admin/stats (Dashboard quick stats)
- POST /api/track (Public visitor tracking - no auth)
- GET /api/admin/analytics/overview (KPI metrics)
- GET /api/admin/analytics/daily (Daily trend data)
- GET /api/admin/analytics/weekly (Weekly comparison)
- GET /api/admin/analytics/top-pages (Top pages visited)
- GET /api/admin/analytics/peak-hours (Peak traffic hours)
- GET /api/admin/analytics/devices (Device breakdown)
- GET /api/admin/analytics/export (CSV download)
- POST /api/enquiries, GET /api/enquiries
- POST /api/testimonials, GET /api/testimonials
- GET /api/admin/testimonials, PATCH /api/admin/testimonials/:id, DELETE /api/admin/testimonials/:id
- POST /api/bookings, GET /api/bookings, PATCH /api/bookings/:id/status

## DB Collections
- enquiries, testimonials, bookings, users (admin auth), visitors (analytics)

## Backlog
- P1: Resend domain verification (user action needed) to send emails to viveksingh9612@gmail.com
- P2: Stripe/Razorpay integration for course fee collection
