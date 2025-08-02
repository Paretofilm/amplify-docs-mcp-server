# AWS Amplify Gen 2 MCP Server - Search Enhancements

## Overview

This document describes the intelligent search and mistake prevention features added to the AWS Amplify Gen 2 MCP documentation server to help developers avoid common pitfalls.

## Key Features Added

### 1. Intent Detection (`detect_query_intent`)
Automatically detects what the user is trying to do:
- **setup**: Creating new projects, initialization
- **auth**: Authorization, permissions, ownership
- **data**: Data modeling, field types, schemas
- **error**: Troubleshooting, issues, problems
- **timestamps**: Date/time handling
- **imports**: Module imports, TypeScript
- **general**: Everything else

### 2. Query Expansion (`expand_query_terms`)
Intelligently expands search terms based on intent:
- "owner" → also searches for "authorization", "allow.owner()", "NOT ownerField"
- "template" → includes "DO NOT clone", "use npx create-next-app"
- "createdAt" → adds "automatic fields", "DO NOT add manually"

### 3. Anti-Pattern Detection (`detect_anti_patterns`)
Detects common mistakes in queries:
- Cloning GitHub template instead of using npx
- Using `.ownerField().identityClaim()` (old syntax)
- Manually managing timestamps
- Using .js extensions in TypeScript imports
- Missing directory creation

### 4. Contextual Warnings (`get_contextual_warnings`)
Provides proactive warnings based on:
- Current file being edited
- Last error encountered
- Search query context

### 5. Relevance Boosting (`calculate_relevance_boost`)
Boosts relevant documentation based on intent:
- Setup docs boosted for setup queries
- Auth patterns boosted for authorization queries
- Troubleshooting boosted for error queries
- Best practices always get a boost

### 6. Enhanced Search Results
- Shows warnings for detected anti-patterns
- Provides contextual help based on intent
- Highlights highly relevant results with ⭐
- Suggests alternatives when no results found
- Tracks search patterns to detect struggling users

### 7. Learning Feedback Loop
- Tracks recent search patterns
- Detects when users are struggling (3 failed searches)
- Offers additional help resources
- Logs patterns for future improvements

## New Tool: `getContextualWarnings`

Usage:
```typescript
getContextualWarnings({
  currentFile: "amplify/data/resource.ts",
  lastError: "ENOENT: no such file or directory",
  searchQuery: "ownerField"
})
```

Returns prioritized warnings:
- 🔴 High Priority: Critical mistakes
- 🟡 Medium Priority: Important issues
- 🟢 Low Priority: Best practice suggestions

## Example: Enhanced Search

Query: "clone template"

Old Response:
```
Found 2 documents matching 'clone template'...
```

New Response:
```
⚠️ **Common Mistakes Detected:**
- Cloning GitHub template: Use npx create-next-app@14.2.10 instead of cloning

🚀 **Project Setup:**
- ✅ Use: `npx create-next-app@14.2.10 your_app_name`
- ❌ Don't: Clone the GitHub template repository

Found 5 documents matching 'clone template':
⭐ 1. Getting Started with Amplify Gen 2 (getting-started)
...
```

## Implementation Approach

1. **Non-Invasive**: Works with existing documentation database
2. **Contextual**: Adapts based on user's current activity
3. **Educational**: Explains why something is wrong
4. **Helpful**: Always provides the correct alternative
5. **Learning**: Improves based on usage patterns

## Benefits

- **Prevents Common Mistakes**: Catches issues before they happen
- **Faster Problem Resolution**: Better search relevance
- **Educational**: Teaches best practices inline
- **Reduces Frustration**: Proactive help when struggling
- **Context-Aware**: Adapts to what developer is doing