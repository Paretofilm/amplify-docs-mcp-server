"""Project detection utilities for Amplify Gen 2 MCP server."""

import re
from typing import Dict, Optional

def should_provide_project_setup(user_query: str) -> bool:
    """Detect if the user wants to create a new project."""
    create_keywords = ['create', 'build', 'start', 'new', 'setup', 'initialize', 'make', 'develop', 'construct']
    project_keywords = ['app', 'application', 'project', 'platform', 'system', 'website', 'site', 'service', 'tool']
    amplify_keywords = ['amplify', 'aws', 'fullstack', 'full-stack', 'serverless']
    
    query_lower = user_query.lower()
    
    # Check for explicit creation intent
    has_create_intent = any(keyword in query_lower for keyword in create_keywords)
    has_project_keyword = any(keyword in query_lower for keyword in project_keywords)
    has_amplify_context = any(keyword in query_lower for keyword in amplify_keywords)
    
    # Return true if creation + project keywords OR if amplify is mentioned with create intent
    return (has_create_intent and has_project_keyword) or (has_amplify_context and has_create_intent)

def detect_required_features(user_query: str) -> Dict[str, any]:
    """Detect what features the user needs based on their query."""
    query_lower = user_query.lower()
    
    return {
        'includeAuth': detects_auth(query_lower),
        'includeData': detects_data(query_lower),
        'includeStorage': detects_storage(query_lower),
        'styling': detect_styling(query_lower) or 'tailwind'  # Default to tailwind
    }

def detects_auth(query: str) -> bool:
    """Check if the query indicates authentication needs."""
    auth_keywords = [
        'auth', 'login', 'user', 'sign', 'account', 'member', 'role', 
        'permission', 'secure', 'private', 'authentication', 'password',
        'register', 'registration', 'profile', 'identity', 'access'
    ]
    return any(keyword in query for keyword in auth_keywords)

def detects_data(query: str) -> bool:
    """Check if the query indicates data/database needs."""
    data_keywords = [
        'data', 'database', 'model', 'store', 'record', 'crud', 'api', 
        'real-time', 'realtime', 'sync', 'save', 'fetch', 'query', 'mutation',
        'graphql', 'rest', 'backend', 'server', 'dynamodb', 'storage', 'persist'
    ]
    return any(keyword in query for keyword in data_keywords)

def detects_storage(query: str) -> bool:
    """Check if the query indicates file storage needs."""
    storage_keywords = [
        'file', 'upload', 'image', 'photo', 'document', 'media', 
        'attachment', 'storage', 'pdf', 'video', 'download', 's3',
        'asset', 'picture', 'gallery', 'portfolio'
    ]
    return any(keyword in query for keyword in storage_keywords)

def detect_styling(query: str) -> Optional[str]:
    """Detect preferred styling framework."""
    if 'tailwind' in query:
        return 'tailwind'
    if 'styled-components' in query or 'styled components' in query:
        return 'styled-components'
    if 'css modules' in query or 'css-modules' in query:
        return 'css-modules'
    if 'sass' in query or 'scss' in query:
        return 'sass'
    if 'plain css' in query or 'vanilla css' in query:
        return 'css'
    return None

def extract_project_name(query: str) -> str:
    """Extract a project name from the user's query."""
    # Common app type patterns
    app_types = {
        'task management': 'task-manager',
        'e-commerce': 'ecommerce',
        'e commerce': 'ecommerce',
        'photo sharing': 'photo-share',
        'photo gallery': 'photo-gallery',
        'real-time chat': 'chat-app',
        'real time chat': 'chat-app',
        'file storage': 'file-storage',
        'social media': 'social-app',
        'blog': 'blog-app',
        'portfolio': 'portfolio',
        'dashboard': 'dashboard',
        'analytics': 'analytics-app'
    }
    
    query_lower = query.lower()
    
    # Check for known app types first
    for pattern, name in app_types.items():
        if pattern in query_lower:
            return name
    
    # Try to extract a reasonable project name from the user's description
    patterns = [
        r"(?:build|create|make|develop)\s+(?:a|an|the)?\s*([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})\s*(?:app|application|platform|system|website|site|service|tool)",
        r"(?:for|called|named)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})",
        r"([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})\s+(?:app|application|platform|system)"
    ]
    
    for pattern in patterns:
        matches = re.search(pattern, query, re.IGNORECASE)
        if matches and matches.group(1):
            # Use underscores instead of dashes
            name = matches.group(1).strip().lower()
            
            # Remove common words that shouldn't be in project names
            stop_words = ['the', 'a', 'an', 'my', 'our', 'your', 'new', 'simple', 'basic', 'aws', 'amplify', 'nextjs', 'next', 'js']
            words = name.split()
            words = [word for word in words if word not in stop_words]
            
            if words:
                # Join with hyphens
                return '-'.join(words)
    
    return 'my-app'

def extract_project_description(query: str) -> str:
    """Extract a human-readable project description."""
    # Remove common prefixes
    query_clean = re.sub(r'^(i want to |help me |please |can you )', '', query.lower())
    query_clean = re.sub(r'^(create|build|make|develop|setup|start) ', '', query_clean)
    
    # Clean up the description
    if query_clean.startswith('a ') or query_clean.startswith('an '):
        query_clean = query_clean[2:].strip()
    
    # If we can't extract anything meaningful, use a generic description
    if not query_clean or len(query_clean) < 3:
        return "your application"
    
    return query_clean

def generate_project_setup_response(user_query: str) -> str:
    """Generate a complete project setup response based on user query."""
    features = detect_required_features(user_query)
    project_name = extract_project_name(user_query)
    project_description = extract_project_description(user_query)
    
    # Generate the response
    response = f"""I'll help you build {project_description} with Amplify Gen 2 and Next.js.

## Step 1: Create Your Project

```bash
npx create-next-app@14.2.10 {project_name} --typescript --app{' --tailwind' if features['styling'] == 'tailwind' else ''} --eslint
cd {project_name}
```

## Step 2: Install Amplify

```bash
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

## Step 3: Set Up Your Backend

Create the backend structure:
```bash
mkdir -p amplify"""
    
    # Add specific directories based on features
    dirs = []
    if features['includeAuth']:
        dirs.append('auth')
    if features['includeData']:
        dirs.append('data')
    if features['includeStorage']:
        dirs.append('storage')
    
    if dirs:
        response += f"/{' amplify/'.join(dirs)}"
    
    response += """
```

**amplify/backend.ts:**
```typescript
import { defineBackend } from '@aws-amplify/backend';"""
    
    # Add imports based on features
    if features['includeAuth']:
        response += "\nimport { auth } from './auth/resource';"
    if features['includeData']:
        response += "\nimport { data } from './data/resource';"
    if features['includeStorage']:
        response += "\nimport { storage } from './storage/resource';"
    
    response += "\n\nexport const backend = defineBackend({"
    
    # Add backend components
    components = []
    if features['includeAuth']:
        components.append('  auth')
    if features['includeData']:
        components.append('  data')
    if features['includeStorage']:
        components.append('  storage')
    
    if components:
        response += "\n" + ",\n".join(components)
    
    response += "\n});\n```\n"
    
    # Add auth configuration if needed
    if features['includeAuth']:
        response += """
**amplify/auth/resource.ts:**
```typescript
import { defineAuth } from '@aws-amplify/backend';

export const auth = defineAuth({
  loginWith: {
    email: true,
  },
});
```
"""
    
    # Add data configuration if needed
    if features['includeData']:
        response += """
**amplify/data/resource.ts:**
```typescript
import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  // Define your data models here
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
});
```
"""
    
    # Add storage configuration if needed
    if features['includeStorage']:
        response += """
**amplify/storage/resource.ts:**
```typescript
import { defineStorage } from '@aws-amplify/backend';

export const storage = defineStorage({
  name: 'myProjectFiles',
  access: (allow) => ({
    'public/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete']),
    ],
  }),
});
```
"""
    
    # Add frontend setup
    response += f"""
## Step 4: Configure Your Frontend

**app/layout.tsx:**
```typescript
import type {{ Metadata }} from "next";
import {{ Inter }} from "next/font/google";
import "./globals.css";
import ConfigureAmplifyClientSide from "./components/ConfigureAmplifyClientSide";

const inter = Inter({{ subsets: ["latin"] }});

export const metadata: Metadata = {{
  title: "{project_name.replace('-', ' ').title()}",
  description: "Built with AWS Amplify and Next.js",
}};

export default function RootLayout({{
  children,
}}: Readonly<{{
  children: React.ReactNode;
}}>) {{
  return (
    <html lang="en">
      <body className={{inter.className}}>
        <ConfigureAmplifyClientSide />
        {{children}}
      </body>
    </html>
  );
}}
```

**app/components/ConfigureAmplifyClientSide.tsx:**
```typescript
"use client";

import {{ Amplify }} from "aws-amplify";
import outputs from "@/amplify_outputs.json";

Amplify.configure(outputs, {{ ssr: true }});

export default function ConfigureAmplifyClientSide() {{
  return null;
}}
```

## Step 5: Start Development

```bash
npx ampx sandbox
```

In a new terminal:
```bash
npm run dev
```

Your {project_description} is now ready for development!"""
    
    return response