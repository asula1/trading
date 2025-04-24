# Auto-Trading System (MSA Architecture)

This project implements an automated cryptocurrency trading system with a Microservice Architecture (MSA) using Docker containers. The system collects real-time market data, makes trading decisions using AI predictions based on deep learning, and manages a cryptocurrency portfolio.

## Architecture Overview

The system is composed of the following microservices:

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Market Data │     │   Trading     │     │ AI Prediction │
│   Service     │     │   Service     │     │ Service       │
│   (8080)      │────▶│   (8081)      │◀───▶│ (8082)        │
└───────▲───────┘     └───────▲───────┘     └───────▲───────┘
        │                     │                     │
        │                     │                     │
        │                     ▼                     │
        │             ┌───────────────┐             │
        │             │  Message      │             │
        └─────────────│  Queue        │─────────────┘
                      │  (RabbitMQ)   │
                      └───────▲───────┘
                              │
                              │
                      ┌───────▼───────┐
┌─────────────┐       │               │       ┌─────────────┐
│             │       │  API Gateway  │       │             │
│  Upbit API  │◀─────▶│  (Nginx:8000) │◀─────▶│  Dashboard  │
│             │       │               │       │  UI         │
└─────────────┘       └───────────────┘       └─────────────┘
```

### Core Services
1. **Market Data Service**: Collects and processes real-time market data from Upbit API
2. **Trading Service**: Manages portfolio and executes trading decisions
3. **AI Prediction Service**: Provides price predictions using deep learning models
4. **API Gateway**: Routes requests between services and hosts the dashboard UI
5. **Message Queue**: Facilitates asynchronous communication between services

### Infrastructure Services
1. **Service Discovery (Consul)**: Enables dynamic service discovery and registration
2. **Event Bus (Kafka)**: Provides event streaming for high-throughput data processing
3. **Database Service (PostgreSQL)**: Persistent storage for trading history and analytics
4. **Distributed Tracing (Jaeger)**: Monitors request flows across services
5. **Monitoring (Prometheus/Grafana)**: System-wide metrics collection and visualization

### Specialized Services
1. **Account Service**: Manages user accounts, authentication, and API key storage
2. **Position Service**: Dedicated service for tracking and managing trading positions
3. **Risk Management Service**: Implements trading limits and emergency procedures
4. **Analysis Services**: Analyzes market trends, patterns, and trading performance
5. **Backtesting Service**: Tests strategies against historical data
6. **Monitoring Services**: Infrastructure and service health monitoring

## Supported Cryptocurrencies

The system currently monitors the following 5 cryptocurrencies:

1. **BTC** - Bitcoin
2. **ETH** - Ethereum
3. **XRP** - Ripple
4. **SOL** - Solana
5. **ADA** - Cardano

## Quick Start

### Prerequisites
- Docker and Docker Compose
- NVIDIA GPU (optional, for accelerated model training)
- NVIDIA Container Toolkit (for GPU support)

### Starting the System
```bash
docker-compose up -d
```

### Accessing the Dashboard
Open a web browser and navigate to:
```
http://localhost:8000
```

### Stopping the System
```bash
docker-compose down
```

## Configuration

### Environment Variables

#### API Authentication
- `UPBIT_ACCESS_KEY`: Your Upbit API access key (optional)
- `UPBIT_SECRET_KEY`: Your Upbit API secret key (optional)

If API keys are not provided, the system will run in simulation mode with mock data.

#### AI Service Configuration
- `TF_CPP_MIN_LOG_LEVEL`: TensorFlow logging level (default: 2)
- `CUDA_VISIBLE_DEVICES`: Specify which GPUs to use (default: 0)
- `TF_FORCE_GPU_ALLOW_GROWTH`: Enable dynamic GPU memory allocation (default: true)

#### Database Configuration
- `POSTGRES_USER`: Database username (default: postgres)
- `POSTGRES_PASSWORD`: Database password (default: postgres)
- `POSTGRES_DB`: Database name (default: trading)

## Security

The system uses JWT authentication to securely communicate with the Upbit API. This requires:
1. Proper JWT token generation with HS512 algorithm (required by Upbit API)
2. Token signature using the Upbit secret key
3. Authorization headers with Bearer token format

## Monitoring

### Dashboard
The dashboard at http://localhost:8000 provides:
- Service status overview
- Portfolio performance
- Real-time market data with 1-second refresh interval
- Current account balance and crypto holdings
- Live trading status including executed trades
- System health metrics
- AI model performance statistics

### Centralized Monitoring
- Prometheus metrics available at http://localhost:9090
- Grafana dashboards at http://localhost:3000
- Jaeger UI for distributed tracing at http://localhost:16686
- Consul UI for service discovery at http://localhost:8500

## Advanced Features

### AI Prediction Model
- Enhanced LSTM deep learning model with multiple layers and 128 units per layer
- Comprehensive technical indicator ensemble (RSI, MACD, Bollinger Bands, Stochastic, ADX, Volatility)
- 6-month historical data (2000+ data points per coin) with 5-minute candles
- Multi-timeframe prediction horizons (1hr, 6hr, 24hr)
- GPU acceleration support for faster model training

### Trading Strategies
- Initial Buy: First purchase based on AI prediction with confidence above 70%
- Take Profit: Automatically sells when profit reaches 1.05% with downward AI prediction
- Stop Loss: Automatically sells when loss exceeds 2%
- Additional Buy: Executes additional purchases at predefined price drops (-1%, -1.5%, -2%)
- Real-time execution of trades without minimum score thresholds

### Risk Management
- Maximum position size enforcement
- Daily loss limits
- Exposure concentration limits
- Market condition monitoring
- Emergency trading halt capability

## Technical Stack

### Backend
- **Python 3.8+**: Core programming language
- **Flask**: Lightweight web framework for microservices
- **TensorFlow 2.10**: Deep learning framework for AI predictions
- **NumPy/Pandas**: Data manipulation and analysis
- **PyJWT**: JWT token generation and validation

### Infrastructure
- **Docker**: Containerization for consistent deployment
- **Docker Compose**: Multi-container application orchestration
- **Nginx**: API gateway and static file serving
- **RabbitMQ**: Message queue for asynchronous communication
- **Kafka**: Event streaming platform
- **PostgreSQL**: Relational database for persistent storage
- **Prometheus/Grafana**: Monitoring and visualization