# Lab Platform Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make terminal-mode lab starts launch a real ttyd-backed Docker container and return its access URL.

**Architecture:** Reuse the existing FastAPI lab route and Docker `ContainerManager`. Add a lab-specific container creation method that accepts the room template image and stores container metadata on `LabSession`.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Docker SDK for Python, SQLite, pytest with fake container manager tests.

---

## File Structure

- Modify `backend/app/services/container_manager.py`: add `create_lab_container`.
- Modify `backend/app/routers/labs.py`: inject the container manager, reject duplicate active sessions, create default limits, launch the lab container, and persist metadata.
- Modify `backend/app/schemas/lab.py`: expose `attacker_container_id` in session responses.
- Modify `backend/tests/test_labs.py`: add route tests using a fake container manager.

---

### Task 1: Test Terminal Lab Launch

- [ ] Add a test that overrides the lab container manager, starts `linux-basics`, and expects the fake container metadata to be persisted and returned.
- [ ] Run the test and confirm it fails because `start_room` still only creates metadata.

### Task 2: Implement Lab Container Launch

- [ ] Add `ContainerManager.create_lab_container(user_id, room_slug, image, limits, exposed_port, github_token)`.
- [ ] Update `/labs/rooms/{slug}/start` to launch the container and return a `running` lab session with `access_url`.
- [ ] Run the Phase 2 tests and confirm they pass.

### Task 3: Prevent Duplicate Active Lab Sessions

- [ ] Add a test that an existing `starting` or `running` lab session returns HTTP 409.
- [ ] Implement duplicate-active-session protection.
- [ ] Run all backend tests.

---

## Self-Review

- Scope is only terminal lab launch. Status, stop, desktop/noVNC, multi-machine networks, and flags remain later phases.
- Tests avoid requiring Docker by injecting a fake container manager.
- The route still uses SQLite and the existing auth dependency.
