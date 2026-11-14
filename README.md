# RPT+: An LLM-powered tutoring system for code refactoring

RPT+ is an intelligent tutoring system that uses Mistral AI to provide personalized feedback and hints on code refactoring exercises within a method.

## Features

- **Interactive Code Exercises**: Practice refactoring in Python, Java, and C#
- **LLM-Powered Feedback**: Get personalized feedback and hints on code submissions using Mistral AI
- **Real-time Code Compilation**: Execute and validate code using Judge0 API
- **User Authentication**: Secure login and session management
- **Responsive Web Interface**: Modern UI built with Vite components
- **Database Persistence**: Store user progress, exercises, and feedback using MySQL

## Project Structure

```
├── backend/                   # FastAPI backend server
│   ├── routers/               # API endpoints (auth, exercises, submissions, feedback)
│   ├── services/              # Business logic (LLM, code execution, diagnosis)
│   ├── migrations/            # Database schema migrations (Alembic)
│   ├── app.py                 # FastAPI application setup
│   ├── database.py            # Database configuration and initialization
│   ├── prompting.py           # LLM configuration and client setup
│   └── schemas.py             # Pydantic data models
├── vite-frontend/             # Vite + JavaScript frontend
│   ├── src/                   # Frontend source code
│   ├── public/                # Static assets
│   └── vite.config.js         # Vite configuration
├── exercise_data/             # Exercise definitions (JSON)
├── tests/                     # Automated tests
└── requirements.txt           # Python dependencies
```

## Prerequisites

- **Python 3.9+** (for backend)
- **Node.js 16+** (for frontend)
- **MySQL 8.0+** (for database)
- API keys for:
  - [Mistral AI](https://console.mistral.ai/)
  - [Judge0](https://judge0.com/) (optional, for code execution)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/eduardo-coliveira/RPT-Plus.git
cd LLM-RPT
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root (see `.env_sample` for reference):

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=rpt_plus

# LLM Configuration
MISTRAL_API_KEY=your_mistral_api_key
MISTRAL_MODEL=mistral-small

# Judge0 Configuration (optional)
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_judge0_api_key
```

### 3. Install Backend Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development and testing
```

### 4. Install Frontend Dependencies

```bash
cd vite-frontend
npm install
cd ..
```

### 5. Initialize the Database

```bash
# Run Alembic migrations
cd backend
alembic upgrade head
cd ..
```

## Running the Application

### Development Mode

Using the Makefile:

```bash
make run_api      # Start FastAPI backend (runs on http://localhost:8000)
make run_server   # Start Vite frontend (runs on http://localhost:5173)
make all          # Run both concurrently
```

Or manually:

**Terminal 1 - Start Backend:**
```bash
uvicorn backend.app:app --reload
```

**Terminal 2 - Start Frontend:**
```bash
cd vite-frontend
npm run dev
```

The API will be available at `http://localhost:8000` and the frontend at `http://localhost:5173`.

### Production Mode

**Build Frontend:**
```bash
cd vite-frontend
npm run build
cd ..
```

**Start Backend:**
```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once the backend is running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

- `POST /rpt-plus/auth/login` - User login
- `POST /rpt-plus/auth/logout` - User logout
- `GET /rpt-plus/exercises` - Get available exercises
- `POST /rpt-plus/submissions` - Submit code for evaluation
- `GET /rpt-plus/feedback/{submission_id}` - Get feedback on submission
- `GET /rpt-plus/actions` - Audit action logs

## Testing

### Backend Tests

```bash
pytest tests/
```

Run specific test file:
```bash
pytest tests/test_api.py -v
```

### Frontend Tests

```bash
cd vite-frontend
npm test
```

## Project Features

### Exercises

The system supports exercises in multiple languages:
- **Python** (`exercise_data/exercises_python.json`)
- **Java** (`exercise_data/exercises_java.json`)
- **C#** (`exercise_data/exercises_csharp.json`)

Exercises include:
- Problem description
- Initial buggy code
- Expected refactored solution
- Test cases for validation

### Code Submission Pipeline

1. User submits code through the web interface
2. Backend validates syntax and executes code via Judge0
3. LLM analyzes code quality and provides feedback
4. System stores submission, feedback, and action logs
5. User receives personalized guidance

## Database Schema

The system uses the following main tables:
- `users` - User accounts and authentication
- `exercises` - Exercise definitions
- `submissions` - Code submissions
- `feedback` - LLM-generated feedback
- `action_logs` - Audit trail of user interactions

Run `alembic current` to view the current migration state.

## Development Workflow

### Adding a New Exercise

1. Create exercise definition in `exercise_data/exercises_*.json`
2. Add corresponding test cases
3. Restart the backend to load new exercises

### Adding Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## Troubleshooting

### Database Connection Issues
- Verify MySQL is running and accessible
- Check `.env` database credentials
- Ensure the database exists: `CREATE DATABASE rpt_plus;`

### LLM API Errors
- Verify Mistral API key is valid
- Check API rate limits
- Review `backend/prompting.py` for configuration

### Frontend Build Issues
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf vite-frontend/dist && npm run build`

## Logging and Monitoring

The system logs all user actions for research purposes:
- Action logs are stored in the database
- Can be exported via the `/rpt-plus/actions` endpoint
- HTML visualization available in `experiment_data/action_log.html`

## License

This project is licensed under the **MIT License**. See the [LICENSE](./LICENSE) file for details.

## Contact

For questions or issues, please open an issue on GitHub or contact the project maintainer.

---

**Repository**: [eduardo-coliveira/RPT-Plus](https://github.com/eduardo-coliveira/RPT-Plus)

