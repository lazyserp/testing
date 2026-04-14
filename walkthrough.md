# Hybrid Seat Booking System — Implementation Walkthrough

The Wissen Hybrid Seat Booking System has been successfully completed, integrating a robust concurrency-safe backend with a responsive, glassmorphic frontend. 

## End-to-End Features Implemented

### 1. The Core 2-Week Cycle Engine
- A highly accurate `schedule_service` determines deterministic cycle rotation based on the ISO week number.
- Employees are accurately assigned 5 office days across each revolving 14-day period. The API accurately resolves the employee's `BatchType` against the day of the week to govern whether they are remote, require a floater, or automatically retain their fixed seat.

### 2. Lock-Synchronized Booking Service
- An inner-memory per-day `asyncio.Lock` mechanism correctly stops race conditions around seat bookings.
- Available floater seats are accurately calculated "just-in-time" by compiling:
  * Baseline floater seats (`F-01` to `F-10`)
  * Fixed seats released actively by users
  * Auto-freed fixed seats attached to users who marked leave
- Enforced strict temporal cutoffs: Bookings, releases, and leaves lock resolutely at **3:00 PM** on the specified day. Tests validated that 4:01 PM requests appropriately bounce back with an HTTP `422 Unprocessable Entity` error.

### 3. Glassmorphic Web App (Frontend)
- **Login Portal**: Highly secure JWT token injection setup relying on `fetch` overrides in the `api.js` class wrapper.
- **Dashboard View**: Calculates and cascades the user's weekly outlook in beautifully designed semantic cards (e.g. `Office Day`, `Remote Day`, `On Leave`), indicating seat requirements clearly.
- **Interactive Seat Map**: Available floater seats render directly into dynamic chips dynamically responding to backend locks and freeing up automatically.

### 4. Admin Toolkit
Using the locked `/api/admin/*` routers, restricted personnel are granted access to:
- Establish Organization-Wide Holidays that instantly override the booking availability table.
- Read daily allocation charts indicating precisely how many people and floaters are situated in the physical office.
- View global system `Audit Logs`.

## Validation Results
Integration testing using `pytest` interacting directly through the `TestClient` confirmed the business edge-cases seamlessly executed:
- > [!TIP]
  > Holiday Override: Verified that introducing a holiday immediately severs the ability for an employee to book a seat, rejecting it securely.
- > [!WARNING]
  > Late Cutoff Trigger: Confirmed releases requested at 4:01 PM are reliably rejected, isolating seat planning variables exactly as required.
- > [!NOTE]
  > Audit Trail Integrity: Validated that `log_action` creates immutable rows upon system shifts reliably inside the locked transactions. 

## Run Instructions
Start your application quickly by navigating to the application root directory:

1. **Start the API Server** (Port 8000)
    ```powershell
    cd backend
    uvicorn main:app --port 8000
    ```

2. **Serve the Frontend HTML** (Port 8080)
    Open a new terminal session in the project root:
    ```powershell
    cd frontend
    python -m http.server 8080
    ```
You can now access the interface via `http://localhost:8080/index.html`. 

*(Sample Credentials)*
**Employee**: `emp.a1.01@wissen.com` / `password123`
**Admin**: `admin@wissen.com` / `admin123`
