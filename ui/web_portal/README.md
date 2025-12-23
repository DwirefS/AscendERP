# ANTS Web Portal

Web-based user interface for interacting with ANTS (AI-Agent Native Tactical System) agents.

## Features

- **Dashboard**: Overview of active agents, system metrics, and health status
- **Agent Marketplace**: Browse and deploy agents from pre-built templates
- **Chat Interface**: Real-time conversations with AI agents
- **Agent Management**: Deploy, configure, and monitor agents
- **Analytics**: View performance metrics, execution history, and swarm coordination
- **System Monitoring**: Real-time system health, resource utilization, and pheromone signals

## Technology Stack

- **Framework**: Next.js 14 (React 18, Server Components, App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Authentication**: Azure AD / MSAL
- **API Communication**: Axios
- **Real-time Updates**: WebSocket (Socket.IO)
- **Charts**: Recharts
- **Icons**: Lucide React

## Getting Started

### Prerequisites

- Node.js >= 18.0.0
- npm >= 9.0.0
- ANTS backend API running

### Installation

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local

# Edit .env.local with your configuration:
# NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
# NEXT_PUBLIC_AZURE_CLIENT_ID=your-azure-client-id
# NEXT_PUBLIC_AZURE_TENANT_ID=your-azure-tenant-id
```

### Development

```bash
# Run development server
npm run dev

# Open browser
# Navigate to http://localhost:3000
```

The portal will automatically connect to the ANTS backend API specified in your environment variables.

### Production Build

```bash
# Build for production
npm run build

# Start production server
npm start

# Or export static site
npm run build
# Static files will be in out/
```

## Project Structure

```
ui/web_portal/
├── src/
│   ├── app/                    # Next.js app router pages
│   │   ├── layout.tsx          # Root layout with navigation
│   │   ├── page.tsx            # Dashboard page
│   │   └── globals.css         # Global styles
│   ├── components/             # React components
│   │   ├── AgentCard.tsx       # Agent card component
│   │   ├── ChatInterface.tsx   # Chat modal component
│   │   ├── SystemMetrics.tsx   # System metrics display
│   │   ├── AgentMarketplace.tsx # Agent marketplace
│   │   ├── Navigation.tsx      # Top navigation bar
│   │   └── AuthProvider.tsx    # Authentication wrapper
│   ├── lib/                    # Utility libraries
│   │   └── api.ts              # ANTS API client
│   ├── hooks/                  # Custom React hooks
│   └── types/                  # TypeScript type definitions
│       └── agent.ts            # Agent-related types
├── public/                     # Static assets
├── package.json                # Dependencies
├── tsconfig.json               # TypeScript config
├── tailwind.config.ts          # Tailwind CSS config
├── next.config.js              # Next.js config
└── README.md                   # This file
```

## Key Components

### Dashboard (`src/app/page.tsx`)

Main dashboard showing:
- System status and health metrics
- Active agents grid
- Agent marketplace
- Quick actions

### AgentCard (`src/components/AgentCard.tsx`)

Displays agent information:
- Agent name, type, and status
- Capabilities
- Performance metrics (tasks completed, success rate, response time)
- Quick actions (Chat, Metrics)

### ChatInterface (`src/components/ChatInterface.tsx`)

Modal chat interface for conversing with agents:
- Real-time message exchange
- Conversation history
- File attachments support
- Typing indicators

### AgentMarketplace (`src/components/AgentMarketplace.tsx`)

Browse and deploy agents:
- Pre-built agent templates
- Filter by category, capability, price tier
- One-click deployment
- Resource requirements display

### API Client (`src/lib/api.ts`)

Centralized API client for backend communication:
- Agent management (get, deploy, stop, delete)
- Conversations (start, send messages, close)
- Marketplace (browse templates, deploy)
- System status and metrics
- Authentication

## API Integration

The portal communicates with the ANTS backend API (typically running on port 8000).

### Available Endpoints

```typescript
// Agent Management
GET    /api/v1/agents                  // List all agents
GET    /api/v1/agents/:id              // Get agent details
POST   /api/v1/agents/deploy           // Deploy new agent
POST   /api/v1/agents/:id/stop         // Stop agent
DELETE /api/v1/agents/:id              // Delete agent

// Conversations
GET    /api/v1/conversations           // List conversations
POST   /api/v1/conversations           // Start conversation
GET    /api/v1/conversations/:id/messages  // Get messages
POST   /api/v1/conversations/:id/messages  // Send message

// Marketplace
GET    /api/v1/marketplace/templates   // List agent templates
GET    /api/v1/marketplace/templates/:id  // Get template details

// System
GET    /api/v1/system/status           // System health status
GET    /api/v1/swarm/metrics            // Swarm coordination metrics
```

## Authentication

The portal uses Azure AD (MSAL) for authentication:

1. User navigates to portal
2. Redirected to Azure AD login
3. After authentication, receives JWT token
4. Token included in all API requests via Authorization header
5. Token refresh handled automatically

Configure Azure AD in `.env.local`:
```
NEXT_PUBLIC_AZURE_CLIENT_ID=your-client-id
NEXT_PUBLIC_AZURE_TENANT_ID=your-tenant-id
```

## Deployment

### Azure Static Web Apps

```bash
# Build the app
npm run build

# Deploy using Azure CLI
az staticwebapp create \
  --name ants-portal \
  --resource-group ants-rg \
  --source . \
  --location eastus \
  --app-location "/" \
  --output-location "out"
```

### Docker

```dockerfile
# Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000
CMD ["npm", "start"]
```

```bash
# Build Docker image
docker build -t ants-portal .

# Run container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://api.ants.com \
  ants-portal
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ants-portal
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ants-portal
  template:
    metadata:
      labels:
        app: ants-portal
    spec:
      containers:
      - name: portal
        image: ants-portal:latest
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_API_URL
          value: "http://ants-api:8000"
---
apiVersion: v1
kind: Service
metadata:
  name: ants-portal
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 3000
  selector:
    app: ants-portal
```

## Customization

### Branding

Update `tailwind.config.ts` to customize colors:

```typescript
colors: {
  primary: {
    // Your brand colors
    500: '#your-color',
    600: '#your-color',
  }
}
```

### Agent Types

Add new agent types in `src/types/agent.ts`:

```typescript
export type AgentType =
  | 'finance'
  | 'security'
  | 'your-custom-type'
```

## Troubleshooting

### Portal can't connect to API

1. Check `.env.local` has correct `NEXT_PUBLIC_API_URL`
2. Verify ANTS backend is running: `curl http://localhost:8000/health`
3. Check CORS settings in backend allow portal origin

### Authentication failing

1. Verify Azure AD configuration in `.env.local`
2. Check app registration in Azure Portal
3. Ensure redirect URIs include portal URL

### Components not rendering

1. Check browser console for errors
2. Verify API responses match TypeScript types
3. Check Network tab for failed requests

## Contributing

When adding new features:

1. Follow existing component structure
2. Add TypeScript types in `src/types/`
3. Update API client in `src/lib/api.ts`
4. Add tests for new components
5. Update this README

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/ants/issues
- Documentation: https://docs.ants.platform
- Email: support@ants.platform
