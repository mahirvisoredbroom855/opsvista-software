# OpsVista — Retrieval-Augmented Generation Platform

<p align="center">
  <img src="pictures/logo.png" alt="OpsVista" height="72">
</p>

<h3 align="center">Intelligent, citation-backed answers over internal documents</h3>
<p align="center">
  Enterprise RAG solution for <strong>Precision Textile Industry LTD (PTIL)</strong>
</p>

<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  </a>
  <a href="https://fastapi.tiangolo.com/">
    <img src="https://img.shields.io/badge/FastAPI-Framework-green.svg" alt="FastAPI">
  </a>
  <a href="https://nextjs.org/">
    <img src="https://img.shields.io/badge/Next.js-Frontend-black.svg" alt="Next.js">
  </a>
  <a href="https://supabase.com/">
    <img src="https://img.shields.io/badge/Supabase-Backend-green.svg" alt="Supabase">
  </a>
  <a href="https://platform.openai.com/">
    <img src="https://img.shields.io/badge/OpenAI-LLM-orange.svg" alt="OpenAI">
  </a>
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Live Environment](#live-environment)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Local Development](#local-development)
- [Building the Enhanced Index](#building-the-enhanced-index)
- [API Documentation](#api-documentation)
- [Frontend Application](#frontend-application)
- [Deployment Guide](#deployment-guide)
- [Security & Compliance](#security--compliance)
- [Monitoring & Operations](#monitoring--operations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Documentation](#documentation)
- [License](#license)

---

## 🔍 Overview

OpsVista is a production-ready **Retrieval-Augmented Generation (RAG)** platform designed to provide intelligent, contextual answers to natural language queries about internal organizational documentation. Built for Precision Textile Industry LTD, the system serves as a unified knowledge interface that consolidates scattered information sources into a searchable, citation-backed question-answering system.


---
## 📖 Documentation

### Technical Documentation
For comprehensive technical details, architectural decisions, and implementation guides, refer to the complete documentation:

**[📄 OpsVista RAG System - Technical Documentation](https://drive.google.com/file/d/16Cxo0c8fKoGjLUDq32pXRK2-sEAt_p6S/view?usp=sharing)**

*This document provides in-depth coverage of:*
- Complete architectural design patterns
- Business requirements and value proposition analysis
- Detailed implementation workflows
- Security framework and compliance guidelines
- Operational procedures and best practices

---

### Business Impact

- **🎯 Unified Knowledge Access**: Consolidates information silos across departments
- **⚡ Instant Response**: Sub-second query processing with intelligent context retrieval
- **📚 Source Attribution**: Every response includes traceable citations to original documents
- **🔄 Operational Resilience**: Dual-path retrieval ensures high availability
- **📈 Scalable Architecture**: Microservices design supporting concurrent users and document growth

<p align="center">
  <img src="pictures/High-Level%20System%20Architecture%20(E2E).png" alt="High-Level Architecture" width="88%">
</p>

---

## 🏗️ Architecture

OpsVista implements a sophisticated dual-path retrieval strategy with provider-agnostic abstractions:

### Core Components

- **🎨 Frontend Layer**: Next.js application with Supabase authentication
- **🚀 API Gateway**: FastAPI application with comprehensive CORS and validation
- **🔍 Retrieval Engine**: Dual-path system (Enhanced Index + Integrated Search)
- **🧠 Generation Layer**: Provider-agnostic LLM client with advanced prompt engineering
- **🔗 External Integrations**: OpenAI APIs, Supabase services, Google Drive

### Retrieval Decision Flow
<p align="center">
  <img src="pictures/Retrieval%20Decision%20Flow%20(Strict).png" alt="Retrieval Decision Flow" width="74%">
</p>

### Response Assembly Process
<p align="center">
  <img src="pictures/Response%20Assembly%20(What%20the%20API%20returns).png" alt="Response Assembly" width="74%">
</p>

---

## ✨ Key Features

### 🎯 Intelligent Retrieval
- **Enhanced Local Index**: Sub-millisecond vector operations via `enhanced_index.json`
- **Integrated Search Fallback**: Adapters to vector DBs, pgvector, and Drive API
- **Quality Assessment**: Automated evaluation with fallback activation

### 📊 Comprehensive Observability
- **Health Monitoring**: Multi-level status endpoints for system, chat, and index
- **Trace Information**: Complete request flow tracking with performance metrics
- **Error Context**: Detailed error reporting with remediation suggestions

### 🔒 Enterprise Security
- **Authentication**: Supabase-powered user management with role-based access
- **Data Protection**: Source attribution without sensitive content logging
- **Audit Trails**: Comprehensive query and response logging

### 🚀 Operational Excellence
- **Provider Agnostic**: Easy switching between LLM providers
- **Graceful Degradation**: Service continuity during external API outages
- **Horizontal Scaling**: Stateless design supporting concurrent operations

---

## 🌐 Live Environment

> **Current Deployment URLs**

| Service | URL | Description |
|---------|-----|-------------|
| 🎨 **Frontend** | `https://opsvista-frontend.vercel.app` | User interface and authentication |
| 🔗 **Backend API** | `https://opsvista-software.onrender.com` | Core API services |
| 📊 **API Base** | `https://opsvista-software.onrender.com/api` | RESTful API endpoints |

---

## 📁 Repository Structure

```
opsvista/
├── 📁 backend/                           # FastAPI backend services
│   ├── 📁 app/
│   │   ├── 📄 main.py                    # FastAPI application entrypoint
│   │   ├── 📁 features/
│   │   │   └── 📁 rag_chatbot/
│   │   │       ├── 📁 api/
│   │   │       │   └── 📄 chat.py        # Chat endpoints (/api/rag/chat/*)
│   │   │       ├── 📁 discovery/         # Document discovery (Drive, local)
│   │   │       ├── 📁 processing/
│   │   │       │   └── 📄 document_processing_engine.py
│   │   │       ├── 📁 chunking/
│   │   │       │   └── 📄 chunking_framework.py
│   │   │       ├── 📁 embedding/
│   │   │       │   └── 📄 embedding_framework.py
│   │   │       └── 📁 vector/
│   │   │           ├── 📄 persisted_inmemory_search.py
│   │   │           ├── 📄 search_integration.py
│   │   │           └── 📄 integrated_search_system.py
│   │   ├── 📁 llm/
│   │   │   └── 📄 llm_client.py          # Provider-agnostic LLM wrapper
│   │   └── 📁 core/                      # Config, database, Supabase client
│   ├── 📄 requirements.txt               # Python dependencies
│   ├── 📄 gdrive_to_enhanced_index.py    # Batch index builder
│   └── 📄 .env                           # Environment variables (local only)
│
├── 📁 frontend/                          # Next.js frontend application
│   └── 📁 src/
│       ├── 📁 app/
│       │   └── 📄 page.tsx               # Main UI component
│       └── 📁 lib/
│           └── 📄 supabaseClient.ts      # Supabase authentication
│
├── 📁 pictures/                          # Documentation assets
│   ├── 📄 logo.png
│   ├── 📄 High-Level System Architecture (E2E).png
│   ├── 📄 Retrieval Decision Flow (Strict).png
│   ├── 📄 Chat Request Sequence (Alt paths shown).png
│   ├── 📄 Response Assembly (What the API returns).png
│   ├── 📄 Integrated Search Composition (Adapters & Clients).png
│   ├── 📄 Data Shape (ER) for Enhanced Index + Metadata.png
│   ├── 📄 Index Build Discovery Pipeline (Drive → Index).png
│   ├── 📄 Infrastructure Runtime Topology.png
│   └── 📄 Health & Diagnostics (Cheap Observability).png
│
└── 📄 README.md                          # This file
```

---

## 🔧 Prerequisites

### System Requirements
- **Python** ≥ 3.11
- **Node.js** ≥ 18 with npm/pnpm
- **Git** for version control

### External Services
- **Supabase Project** (Authentication + PostgreSQL)
- **OpenAI API Key** (LLM + embeddings) - *optional for development with mocks*
- **Google Drive Service Account** - *optional for Drive document sources*

---

## ⚙️ Environment Configuration

### Backend Configuration

Create `backend/.env` for local development:

```bash
# 🔑 Core Services
OPENAI_API_KEY=sk-proj-...                 # Optional for dev with mocks
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service-role-key>

# 🌐 CORS Configuration
CORS_ORIGINS=https://opsvista-frontend.vercel.app,https://<preview>.vercel.app

# 📄 Document Sources
GOOGLE_CREDENTIALS_PATH=/absolute/path/to/service-account.json

# 🗂️ Enhanced Index Configuration
ENHANCED_INDEX_PATH=./enhanced_index.json
EMBEDDING_MODEL=text-embedding-3-small
TOP_K=4
```

### Frontend Configuration

Create `frontend/.env.local`:

```bash
# 🔗 API Configuration
NEXT_PUBLIC_API_BASE_URL=https://opsvista-software.onrender.com/api

# 🔐 Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anonymous-key>
```

---

## 🚀 Local Development

### 1️⃣ Clone and Setup

```bash
# Clone repository
git clone <repository-url> opsvista
cd opsvista

# Setup Python environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install backend dependencies
pip install -r backend/requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 2️⃣ Configure Environment

Set up environment files as described in [Environment Configuration](#environment-configuration).

### 3️⃣ Build Enhanced Index

```bash
# Build initial index (run from repository root with venv active)
python backend/gdrive_to_enhanced_index.py
```

### 4️⃣ Start Backend Service

```bash
# Start FastAPI development server
uvicorn app.main:app --app-dir backend --reload --port 8000

# API available at: http://127.0.0.1:8000/api
# Documentation: http://127.0.0.1:8000/docs
```

### 5️⃣ Start Frontend Application

```bash
# Start Next.js development server
cd frontend
npm run dev

# UI available at: http://localhost:3000
```

---

## 🗂️ Building the Enhanced Index

The Enhanced Index transforms documents into searchable vector representations stored in `enhanced_index.json`.

### Index Build Pipeline
<p align="center">
  <img src="pictures/Index%20Build%20Discovery%20Pipeline.png" alt="Index Build Pipeline" width="72%">
</p>

### Trigger Methods

#### 📊 Batch Script (Recommended)
```bash
# From repository root with virtual environment active
python backend/gdrive_to_enhanced_index.py
```

#### 🔗 API Endpoint
```bash
curl -X POST "${API_BASE}/rag/discover" \
  -H "Content-Type: application/json"
```

### Data Structure
<p align="center">
  <img src="pictures/Data%20Shape%20(ER)%20for%20Enhanced%20Index%20+%20Metadata.png" alt="Data Shape" width="68%">
</p>

### Processing Pipeline

1. **🔍 Document Discovery**: Automated scanning of Drive and local sources
2. **📝 Content Processing**: Multi-format support (PDF, DOCX, TXT, etc.)
3. **✂️ Intelligent Chunking**: Semantic boundary detection with context preservation
4. **🧠 Embedding Generation**: Vector representations via OpenAI embeddings
5. **💾 Index Persistence**: Optimized JSON structure for rapid similarity search

---

## 📚 API Documentation

### Base Configuration
```
API_BASE = https://opsvista-software.onrender.com/api
```

### Health & Status Endpoints

#### System Health Check
```http
GET ${API_BASE}/status
```
**Response**: Overall application health without external dependencies

#### Chat Service Status
```http
GET ${API_BASE}/rag/chat/status
```
**Response**: Retrieval engine and LLM provider availability

#### Enhanced Index Status
```http
GET ${API_BASE}/rag/chat/index/status
```
**Response**: Index metadata, size, modification time, and embedding statistics

<p align="center">
  <img src="pictures/Health%20%26%20Diagnostics%20(Cheap%20Observability).png" alt="Health & Diagnostics" width="66%">
</p>

### RAG Chat Endpoints

#### Complete Chat Request
```http
POST ${API_BASE}/rag/chat/complete
Content-Type: application/json

{
  "message": "Summarize the onboarding policy for new textile engineers",
  "top_k": 4,
  "debug": true
}
```

#### Response Structure
```json
{
  "content": "Based on the onboarding documentation...",
  "sources": [
    {
      "title": "Engineering Onboarding Policy",
      "origin": "Google Drive",
      "path": "/HR/Policies/Engineering_Onboarding_v2.pdf",
      "relevance_score": 0.87
    }
  ],
  "usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 567,
    "total_tokens": 1801
  },
  "trace": {
    "impl": "EnhancedIndex",
    "index_path": "enhanced_index.json",
    "used_fallback": false,
    "processing_time_ms": 245,
    "warnings": []
  }
}
```

### Chat Request Sequence
<p align="center">
  <img src="pictures/Chat%20Request%20Sequence%20(Alt%20paths%20shown).png" alt="Chat Request Sequence" width="86%">
</p>

---

## 🎨 Frontend Application

### Core Components

#### Main Interface
- **Location**: `frontend/src/app/page.tsx`
- **Features**: Chat UI, response rendering, citation display, trace information
- **Styling**: Tailwind CSS with responsive design

#### Authentication Client
- **Location**: `frontend/src/lib/supabaseClient.ts`
- **Features**: User sign-in/sign-up, session management, protected routes

### Key Features

- **💬 Intelligent Chat Interface**: Natural language query processing
- **📋 Citation Display**: Interactive source links with relevance scores
- **🔍 Trace Information**: Processing details for debugging and optimization
- **🔐 Secure Authentication**: Supabase-powered user management
- **📱 Responsive Design**: Optimized for desktop and mobile devices

---

## 🚀 Deployment Guide

### Infrastructure Topology
<p align="center">
  <img src="pictures/Infrastructure%20Runtime%20Topology.png" alt="Infrastructure Topology" width="80%">
</p>

### Backend Deployment (Render)

#### Service Configuration
1. **Create Web Service** from `backend/` directory
2. **Configure Build Settings**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

#### Environment Variables
```bash
OPENAI_API_KEY=sk-proj-...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service-role-key>
CORS_ORIGINS=https://opsvista-frontend.vercel.app
ENHANCED_INDEX_PATH=./enhanced_index.json
EMBEDDING_MODEL=text-embedding-3-small
TOP_K=4
```

#### Health Check Configuration
- **Health Check Path**: `/api/status`
- **Expected Status Code**: `200`

### Frontend Deployment (Vercel)

#### Project Setup
1. **Import Repository** with root directory set to `frontend/`
2. **Configure Build Settings**:
   - **Framework Preset**: Next.js
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`

#### Environment Variables
```bash
NEXT_PUBLIC_API_BASE_URL=https://opsvista-software.onrender.com/api
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anonymous-key>
```

### Post-Deployment Checklist

- [ ] **CORS Configuration**: Verify frontend domains in backend `CORS_ORIGINS`
- [ ] **API Connectivity**: Test `/api/status` endpoint accessibility
- [ ] **Authentication Flow**: Validate Supabase login/logout functionality
- [ ] **Chat Functionality**: Execute test queries and verify responses
- [ ] **Health Monitoring**: Configure uptime monitoring for all endpoints

---

## 🔒 Security & Compliance

### Authentication & Authorization
- **🔐 Supabase Integration**: Enterprise-grade user management with JWT tokens
- **🛡️ Role-Based Access**: Extensible permission system for document access control
- **🔑 API Security**: Request validation, rate limiting, and CORS policies

### Data Protection
- **📄 Source Preservation**: Original documents remain in source locations
- **🗂️ Metadata Only**: Index stores text chunks and references, not full documents
- **📝 Audit Trails**: Comprehensive logging of queries and responses
- **🚫 PII Protection**: Sensitive content filtering and secure logging practices

### Compliance Features
- **📊 Query Logging**: Timestamped user interactions with pseudonymous IDs
- **🔍 Source Attribution**: Complete provenance tracking for all responses
- **⏱️ Data Retention**: Configurable retention policies for audit requirements
- **🔒 Secure Transport**: HTTPS enforcement across all service communications

---

## 📊 Monitoring & Operations

### Observability Strategy

#### Multi-Level Health Assessment
- **🟢 System Status**: Application health without external dependencies
- **🔍 Service Status**: Retrieval and LLM provider availability
- **📊 Index Status**: Content metadata and performance metrics

#### Comprehensive Trace Information
```json
{
  "trace": {
    "impl": "EnhancedIndex|IntegratedSearch",
    "index_path": "enhanced_index.json",
    "used_fallback": false,
    "processing_time_ms": 245,
    "query_tokens": 15,
    "retrieval_confidence": 0.87,
    "warnings": []
  }
}
```

### Operational Best Practices

#### Backup Strategy
- **📁 Enhanced Index**: Daily versioned backups with off-site storage
- **🗄️ PostgreSQL**: Supabase managed backups with point-in-time recovery
- **📋 Configuration**: Environment variables and secrets backup

#### Scaling Considerations
- **🔄 Horizontal Scaling**: Stateless backend design supports load balancing
- **⚡ Performance**: Enhanced index provides consistent sub-second response times
- **💰 Cost Optimization**: Intelligent rate limiting and batch processing

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### CORS Configuration Issues
**Problem**: Frontend cannot access backend API
**Solution**: 
```bash
# Verify CORS_ORIGINS includes exact frontend domains
CORS_ORIGINS=https://opsvista-frontend.vercel.app,https://preview-branch.vercel.app
```

#### Enhanced Index Problems
**Problem**: "Enhanced index not found" or zero results
**Solution**:
```bash
# Check index status
curl GET "${API_BASE}/rag/chat/index/status"

# Rebuild index
python backend/gdrive_to_enhanced_index.py
```

#### Authentication Failures
**Problem**: Supabase authentication not working
**Solution**:
- Verify `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Check Supabase project RLS policies
- Validate JWT token expiration settings

#### Embedding Dimension Mismatch
**Problem**: "Shapes not aligned" during retrieval
**Solution**:
- Ensure consistent embedding model across index build and search
- Rebuild index with correct `EMBEDDING_MODEL` setting
- Verify OpenAI API key has access to specified model

#### Performance Issues
**Problem**: Slow response times
**Solution**:
- Check enhanced index file size and load times
- Monitor OpenAI API rate limits and quotas
- Verify adequate system resources for embedding operations

### Debug Mode

Enable detailed logging by setting `debug: true` in chat requests:

```json
{
  "message": "Your query here",
  "debug": true
}
```

This provides comprehensive trace information for troubleshooting.

---

## 🤝 Contributing

### Development Guidelines

#### Code Standards
- **Python**: Follow PEP 8 style guidelines with Black formatting
- **TypeScript**: ESLint configuration with Prettier formatting
- **Documentation**: Comprehensive docstrings and inline comments

#### Testing Requirements
- **Unit Tests**: Minimum 80% code coverage for core functionality
- **Integration Tests**: End-to-end API testing with mock services
- **Performance Tests**: Load testing for concurrent user scenarios

#### Pull Request Process
1. **🌿 Feature Branch**: Create from `main` with descriptive naming
2. **✅ Testing**: Ensure all tests pass and coverage requirements met
3. **📚 Documentation**: Update relevant documentation and README sections
4. **🔍 Code Review**: Minimum two reviewer approvals required
5. **🚀 Deployment**: Automated CI/CD pipeline handles staging deployment

### Development Environment Setup

```bash
# Install development dependencies
pip install -r backend/requirements-dev.txt

# Setup pre-commit hooks
pre-commit install

# Run tests
pytest backend/tests/

# Format code
black backend/
prettier --write frontend/
```

---

## 📄 License

**Proprietary Software** - © 2025 Precision Textile Industry LTD

This repository contains proprietary materials of Precision Textile Industry LTD (PTIL). All rights reserved. No part of this software, documentation, or associated materials may be reproduced, distributed, or transmitted in any form without prior written permission from PTIL.

### Authorized Personnel Only
Access to this repository and its contents is restricted to authorized PTIL personnel and approved contractors bound by confidentiality agreements.

### Third-Party Components
This software incorporates open-source components under their respective licenses. See individual component documentation for specific license terms.

---

<div align="center">

**Built with ❤️ for Precision Textile Industry LTD**

*For support or questions, contact the OpsVista Engineering Team*

</div>