---
author: Alice Smith
---

# Architecture Overview

## Backend Design

The backend uses a FastAPI framework with SQLAlchemy for ORM. We chose FastAPI for its async support and automatic OpenAPI docs.

### Database

We use SQLite for development and PostgreSQL for production. The migration strategy is handled by Alembic.

## Frontend Design

React with TypeScript and Vite for build tooling. We use Tailwind CSS for styling and React Router for navigation.

### State Management

We use React Query for server state and React Context for local UI state. No Redux needed for our scale.

## Deployment

Docker Compose for local dev, Kubernetes for production. CI/CD is handled by GitHub Actions.
