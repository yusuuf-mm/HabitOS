# 📸 Screenshot Placement Guide

This guide shows exactly where to add screenshots to the README for maximum impact.

## 🎯 High Priority Screenshots

### 1. Dashboard Screenshot

**File Location**: `docs/images/dashboard-screenshot.png`

**README Location**: Line 7 (right after the header)

**Current Code**:
```markdown
<!-- TODO: Add screenshot of the application dashboard here -->
<!-- Suggested location: docs/images/dashboard-screenshot.png -->
![HabitOS Dashboard](./docs/images/dashboard-screenshot.png)
```

**What to Capture**:
- Open https://habitos-bnnl.onrender.com
- Login or register
- Navigate to the dashboard
- Take a full-width screenshot showing:
  - Stats cards at the top
  - Charts/graphs
  - Recent behaviors list
  - Today's schedule

**Why It Matters**: This is the FIRST thing visitors see. A professional dashboard screenshot immediately demonstrates the application's value and quality.

---

### 2. Architecture Diagram

**File Location**: `docs/images/architecture-diagram.png`

**README Location**: After "System Architecture" heading (around line 220)

**Current Code**:
```markdown
<!-- TODO: Add architecture diagram here -->
<!-- Suggested location: docs/images/architecture-diagram.png -->
```

**How to Create**:

**Option A: Use the Mermaid Diagram**
The README already includes a Mermaid diagram. GitHub will render it automatically, so you could just add:

```markdown
*Mermaid diagram renders automatically on GitHub*
```

**Option B: Create a Professional PNG**
- Use tools like:
  - Figma (https://figma.com)
  - Draw.io (https://app.diagrams.net)
  - Excalidraw (https://excalidraw.com)
- Create a visual diagram showing:
  - Client Layer (Browser)
  - Frontend Layer (React, Router, State, Query)
  - API Gateway (Nginx)
  - Backend Services (Auth, Behaviors, Optimization, Analytics)
  - Optimization Engine (PuLP, CBC)
  - Data Layer (PostgreSQL, Redis)
- Use colors to differentiate layers
- Add icons for each technology

**Why It Matters**: Visual architecture helps developers quickly understand system complexity and technology choices.

---

## 🎨 Optional Screenshots (Nice to Have)

### 3. Optimization Results

**File Location**: `docs/images/optimization-results.png`

**Where to Add**: In "Mathematical Foundation" section after the example output

**What to Capture**:
- Run an optimization from the UI
- Screenshot the results showing:
  - Scheduled behaviors in timeline view
  - Objective contribution breakdown
  - Total score and execution time
  - Energy/time usage charts

---

### 4. Swagger UI Documentation

**File Location**: `docs/images/swagger-ui.png`

**Where to Add**: In "API Documentation" section after the Interactive Docs links

**What to Capture**:
- Open https://habitos-bnnl.onrender.com/docs
- Expand a few endpoint sections (e.g., Auth, Behaviors)
- Screenshot showing:
  - Endpoint list
  - Request/response schemas
  - Try it out interface

---

### 5. Behavior Creation Form

**File Location**: `docs/images/behavior-form.png`

**Where to Add**: Could add a "Screenshots" or "User Interface" section near the end

**What to Capture**:
- Open the "Create Behavior" form
- Fill it with sample data
- Screenshot showing all form fields and validation

---

## 📁 Directory Structure Setup

Create the images directory:

```bash
mkdir -p /workspaces/HabitOS/docs/images
```

Then add your screenshots here:

```
/workspaces/HabitOS/
├── docs/
│   ├── images/
│   │   ├── dashboard-screenshot.png         # Priority 1
│   │   ├── architecture-diagram.png         # Priority 2
│   │   ├── optimization-results.png         # Optional
│   │   ├── swagger-ui.png                   # Optional
│   │   └── behavior-form.png                # Optional
│   └── ...
├── README.md
└── ...
```

---

## 🎬 How to Take Great Screenshots

### For Dashboard & UI Screenshots

1. **Use Full-Width Browser**
   - Set browser width to 1920px (standard desktop)
   - Use browser dev tools to set exact viewport size

2. **Remove Distractions**
   - Hide browser chrome (press F11 for fullscreen mode)
   - Close unnecessary tabs
   - Disable browser extensions that show in the UI

3. **Use Real Data**
   - Don't use "Lorem ipsum" or fake data
   - Create realistic behaviors, schedules, and objectives
   - Show meaningful charts with actual data

4. **Capture High Quality**
   - Use PNG format (not JPG)
   - Ensure high resolution (at least 1920x1080)
   - Avoid blurry or pixelated images

5. **Consider Dark Mode**
   - If your app has dark mode, consider showing both
   - Dark mode screenshots often look more professional

### For Diagrams

1. **Use Professional Tools**
   - Figma, Draw.io, Excalidraw, or Mermaid
   - Maintain consistent styling and colors

2. **Keep It Simple**
   - Don't overcomplicate the diagram
   - Use clear labels and arrows
   - Group related components

3. **Export at High Resolution**
   - Export at 2x or 3x resolution for retina displays
   - Use PNG with transparent background if possible

---

## ✅ Quick Checklist

Before adding screenshots to the README:

- [ ] Screenshots are PNG format
- [ ] Resolution is at least 1920x1080
- [ ] Images are saved in `docs/images/` directory
- [ ] File names match what's in the README
- [ ] Screenshots show real, meaningful data
- [ ] No sensitive information visible (passwords, API keys, etc.)
- [ ] Images are compressed (use tools like TinyPNG if needed)
- [ ] README markdown references correct file paths

---

## 🔧 Creating the Images Directory

Run this command to create the directory structure:

```bash
mkdir -p /workspaces/HabitOS/docs/images
```

Then you can add images:

```bash
# Example: Adding a screenshot
cp /path/to/your/screenshot.png /workspaces/HabitOS/docs/images/dashboard-screenshot.png
```

---

## 📝 After Adding Screenshots

Once you've added the screenshots, remove the TODO comments from the README:

**Before**:
```markdown
<!-- TODO: Add screenshot of the application dashboard here -->
<!-- Suggested location: docs/images/dashboard-screenshot.png -->
![HabitOS Dashboard](./docs/images/dashboard-screenshot.png)
```

**After**:
```markdown
![HabitOS Dashboard](./docs/images/dashboard-screenshot.png)
```

The image will now display beautifully in the README! 🎉
