#!/usr/bin/env python3
"""
Documentation Index Generator for Amplify MCP Server

This module creates a comprehensive index of all documentation with:
- Hierarchical structure
- Brief summaries for each section
- Quick navigation aids
- Pattern detection
"""

import json
import sqlite3
from typing import Dict, List, Any, Optional
from pathlib import Path
import re
from collections import defaultdict

class DocumentationIndexer:
    """Creates and manages a comprehensive documentation index."""
    
    def __init__(self, db_path: str = "amplify_docs.db"):
        self.db_path = db_path
        self.index = {
            "overview": "",
            "categories": {},
            "quick_access": {},
            "patterns": {},
            "components": {},
            "common_tasks": {}
        }
    
    def generate_index(self) -> Dict[str, Any]:
        """Generate a comprehensive index of all documentation."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all documents
        cursor.execute("""
            SELECT url, title, content, markdown_content, category
            FROM documents
            ORDER BY category, title
        """)
        
        documents = cursor.fetchall()
        
        # Build category structure
        category_docs = defaultdict(list)
        for doc in documents:
            url, title, content, markdown, category = doc
            category_docs[category].append({
                "url": url,
                "title": title,
                "content": content,
                "markdown": markdown,
                "summary": self._generate_summary(content, title)
            })
        
        # Create hierarchical index
        for category, docs in category_docs.items():
            self.index["categories"][category] = {
                "title": self._format_category_name(category),
                "doc_count": len(docs),
                "summary": self._generate_category_summary(category, docs),
                "sections": self._organize_sections(docs),
                "key_topics": self._extract_key_topics(docs)
            }
        
        # Generate quick access patterns
        self.index["quick_access"] = self._generate_quick_access()
        
        # Extract common patterns
        self.index["patterns"] = self._extract_patterns(documents)
        
        # Identify UI components
        self.index["components"] = self._identify_components(documents)
        
        # Common tasks mapping
        self.index["common_tasks"] = self._map_common_tasks(documents)
        
        # Generate overview
        self.index["overview"] = self._generate_overview()
        
        conn.close()
        return self.index
    
    def _generate_summary(self, content: str, title: str) -> str:
        """Generate a brief summary of document content."""
        # Clean content
        content = re.sub(r'```[\s\S]*?```', '', content)  # Remove code blocks
        content = re.sub(r'`[^`]+`', '', content)  # Remove inline code
        
        # Extract first meaningful paragraph
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
        
        if paragraphs:
            summary = paragraphs[0][:200] + "..."
        else:
            summary = f"Documentation for {title}"
        
        return summary
    
    def _format_category_name(self, category: str) -> str:
        """Format category name for display."""
        category_names = {
            "backend": "Backend Development",
            "frontend": "Frontend & UI",
            "getting-started": "Getting Started",
            "general": "General Documentation",
            "reference": "API Reference",
            "deployment": "Deployment & Hosting",
            "auth": "Authentication & Authorization",
            "storage": "File Storage",
            "api": "API Development"
        }
        return category_names.get(category, category.replace("-", " ").title())
    
    def _generate_category_summary(self, category: str, docs: List[Dict]) -> str:
        """Generate summary for a category."""
        summaries = {
            "backend": "Build scalable serverless backends with AWS services. Covers data modeling, API development, authentication, storage, and serverless functions.",
            "frontend": "Create responsive UIs with Amplify UI components, implement client-side data fetching, and integrate with backend services.",
            "getting-started": "Quick start guides and tutorials to get your Amplify + Next.js application up and running.",
            "general": "Core concepts, architecture overview, and general Amplify documentation.",
            "reference": "Detailed API references, configuration options, and technical specifications.",
            "deployment": "Deploy your application to AWS, configure custom domains, and set up CI/CD pipelines.",
            "auth": "Implement secure authentication flows, manage user sessions, and configure authorization rules.",
            "storage": "Upload, download, and manage files with Amazon S3 integration.",
            "api": "Build GraphQL and REST APIs with real-time subscriptions and custom business logic."
        }
        return summaries.get(category, f"Documentation for {self._format_category_name(category)}")
    
    def _organize_sections(self, docs: List[Dict]) -> Dict[str, List[Dict]]:
        """Organize documents into logical sections."""
        sections = defaultdict(list)
        
        for doc in docs:
            # Extract section from URL or title
            url_parts = doc["url"].split("/")
            
            # Try to identify subsection
            if len(url_parts) > 5:
                section = url_parts[5]
            else:
                # Fallback to title analysis
                title_lower = doc["title"].lower()
                if "setup" in title_lower or "install" in title_lower:
                    section = "setup"
                elif "api" in title_lower or "graphql" in title_lower:
                    section = "api"
                elif "auth" in title_lower:
                    section = "authentication"
                elif "storage" in title_lower or "s3" in title_lower:
                    section = "storage"
                elif "data" in title_lower or "model" in title_lower:
                    section = "data"
                else:
                    section = "other"
            
            sections[section].append({
                "title": doc["title"],
                "url": doc["url"],
                "summary": doc["summary"]
            })
        
        return dict(sections)
    
    def _extract_key_topics(self, docs: List[Dict]) -> List[str]:
        """Extract key topics from documents."""
        topics = set()
        
        # Common keywords to look for
        keywords = [
            "authentication", "api", "graphql", "rest", "storage", "s3",
            "database", "dynamodb", "lambda", "function", "deployment",
            "hosting", "authorization", "cognito", "iam", "amplify",
            "data", "model", "schema", "subscription", "mutation",
            "query", "resolver", "file", "upload", "download"
        ]
        
        for doc in docs:
            content_lower = doc["content"].lower()
            for keyword in keywords:
                if keyword in content_lower:
                    topics.add(keyword)
        
        return sorted(list(topics))
    
    def _generate_quick_access(self) -> Dict[str, Any]:
        """Generate quick access shortcuts."""
        return {
            "create_app": {
                "title": "Create New App",
                "command": "npx create-amplify@latest --template nextjs",
                "description": "Start a new Amplify Gen 2 + Next.js application"
            },
            "add_auth": {
                "title": "Add Authentication",
                "path": "/build-a-backend/auth/set-up-auth/",
                "description": "Set up user authentication with Amazon Cognito"
            },
            "add_api": {
                "title": "Add API",
                "path": "/build-a-backend/data/",
                "description": "Create GraphQL or REST APIs"
            },
            "add_storage": {
                "title": "Add Storage",
                "path": "/build-a-backend/storage/",
                "description": "Configure file storage with S3"
            },
            "deploy": {
                "title": "Deploy App",
                "path": "/deploy-and-host/",
                "description": "Deploy to AWS Amplify Hosting"
            }
        }
    
    def _extract_patterns(self, documents: List) -> Dict[str, List[Dict]]:
        """Extract common code patterns from documentation."""
        patterns = defaultdict(list)
        
        pattern_markers = {
            "auth": ["signIn", "signOut", "getCurrentUser", "Authenticator"],
            "api": ["GraphQL", "API.graphql", "defineData", "mutation", "query"],
            "storage": ["uploadData", "downloadData", "getUrl", "Storage"],
            "data": ["defineData", "a.model", "schema", "authorization"]
        }
        
        for doc in documents:
            url, title, content, markdown, category = doc
            
            for pattern_type, markers in pattern_markers.items():
                if any(marker in content for marker in markers):
                    # Extract code examples
                    code_blocks = re.findall(r'```(?:typescript|javascript|tsx|jsx)?\n([\s\S]*?)```', markdown or content)
                    
                    if code_blocks:
                        patterns[pattern_type].append({
                            "title": title,
                            "url": url,
                            "examples": code_blocks[:2]  # First 2 examples
                        })
        
        return dict(patterns)
    
    def _identify_components(self, documents: List) -> Dict[str, List[Dict]]:
        """Identify UI components mentioned in documentation."""
        components = defaultdict(list)
        
        # Amplify UI components
        ui_components = [
            "Authenticator", "StorageImage", "StorageManager", "FileUploader",
            "AccountSettings", "Collection", "Table", "Tabs", "Alert",
            "Badge", "Button", "Card", "CheckboxField", "Divider",
            "Flex", "Grid", "Heading", "Icon", "Image", "Link",
            "Loader", "Menu", "Pagination", "PhoneNumberField",
            "Placeholder", "Radio", "RadioGroupField", "Rating",
            "SearchField", "SelectField", "SliderField", "StepperField",
            "SwitchField", "Text", "TextAreaField", "TextField",
            "ToggleButton", "ToggleButtonGroup", "View", "VisuallyHidden"
        ]
        
        for doc in documents:
            url, title, content, _, _ = doc
            
            for component in ui_components:
                if component in content:
                    components[component].append({
                        "url": url,
                        "title": title,
                        "usage_context": self._extract_component_context(content, component)
                    })
        
        return dict(components)
    
    def _extract_component_context(self, content: str, component: str) -> str:
        """Extract usage context for a component."""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if component in line:
                # Get surrounding context
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context = '\n'.join(lines[start:end])
                return context[:200] + "..."
        return f"Usage of {component} component"
    
    def _map_common_tasks(self, documents: List) -> Dict[str, Dict]:
        """Map common developer tasks to relevant documentation."""
        tasks = {
            "setup_authentication": {
                "description": "Set up user authentication",
                "keywords": ["auth", "cognito", "signin", "signup"],
                "categories": ["backend", "auth"]
            },
            "create_api": {
                "description": "Create GraphQL or REST API",
                "keywords": ["api", "graphql", "rest", "endpoint"],
                "categories": ["backend", "api"]
            },
            "upload_files": {
                "description": "Handle file uploads",
                "keywords": ["storage", "upload", "s3", "file"],
                "categories": ["backend", "storage"]
            },
            "deploy_app": {
                "description": "Deploy application",
                "keywords": ["deploy", "hosting", "amplify console"],
                "categories": ["deployment"]
            },
            "manage_data": {
                "description": "Work with databases",
                "keywords": ["data", "model", "schema", "dynamodb"],
                "categories": ["backend", "data"]
            }
        }
        
        # Find relevant docs for each task
        for task_id, task in tasks.items():
            task["relevant_docs"] = []
            
            for doc in documents:
                url, title, content, _, category = doc
                content_lower = content.lower()
                
                # Check if doc matches task
                if any(keyword in content_lower for keyword in task["keywords"]):
                    task["relevant_docs"].append({
                        "url": url,
                        "title": title,
                        "relevance": sum(1 for kw in task["keywords"] if kw in content_lower)
                    })
            
            # Sort by relevance
            task["relevant_docs"].sort(key=lambda x: x["relevance"], reverse=True)
            task["relevant_docs"] = task["relevant_docs"][:5]  # Top 5
        
        return tasks
    
    def _generate_overview(self) -> str:
        """Generate comprehensive overview text."""
        total_docs = sum(cat["doc_count"] for cat in self.index["categories"].values())
        
        overview = f"""# AWS Amplify Gen 2 Documentation for Next.js

## Overview
This documentation server provides access to {total_docs} documents covering AWS Amplify Gen 2 integration with Next.js applications.

## Main Categories
"""
        
        for cat_id, cat_data in self.index["categories"].items():
            overview += f"\n### {cat_data['title']} ({cat_data['doc_count']} docs)\n"
            overview += f"{cat_data['summary']}\n"
            
            if cat_data.get("key_topics"):
                overview += f"**Key Topics:** {', '.join(cat_data['key_topics'][:5])}\n"
        
        overview += "\n## Quick Start\n"
        overview += "```bash\nnpx create-amplify@latest --template nextjs\n```\n"
        
        overview += "\n## Common Tasks\n"
        for task_id, task in self.index["common_tasks"].items():
            if task.get("relevant_docs"):
                overview += f"- **{task['description']}**: {task['relevant_docs'][0]['title']}\n"
        
        return overview
    
    def save_index(self, output_path: str = "documentation_index.json"):
        """Save the index to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
        
        print(f"Index saved to {output_path}")
    
    def create_summary_table(self):
        """Create a summary table in the database for quick lookups."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                category TEXT,
                topics TEXT,
                patterns TEXT,
                components TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Populate summaries
        cursor.execute("SELECT url, title, content, category FROM documents")
        
        for row in cursor.fetchall():
            url, title, content, category = row
            
            summary = self._generate_summary(content, title)
            topics = json.dumps(self._extract_topics_from_content(content))
            patterns = json.dumps(self._extract_patterns_from_content(content))
            components = json.dumps(self._extract_components_from_content(content))
            
            cursor.execute("""
                INSERT OR REPLACE INTO document_summaries
                (url, title, summary, category, topics, patterns, components)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (url, title, summary, category, topics, patterns, components))
        
        conn.commit()
        conn.close()
        
        print("Summary table created successfully")
    
    def _extract_topics_from_content(self, content: str) -> List[str]:
        """Extract topics from content."""
        topics = []
        topic_keywords = {
            "authentication": ["auth", "signin", "signup", "cognito"],
            "api": ["graphql", "rest", "endpoint", "mutation", "query"],
            "storage": ["s3", "upload", "download", "file"],
            "data": ["model", "schema", "database", "dynamodb"],
            "deployment": ["deploy", "hosting", "build"],
            "functions": ["lambda", "function", "serverless"]
        }
        
        content_lower = content.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in content_lower for kw in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_patterns_from_content(self, content: str) -> List[str]:
        """Extract code patterns from content."""
        patterns = []
        pattern_signatures = {
            "auth_pattern": ["signIn(", "signOut(", "getCurrentUser("],
            "api_pattern": ["API.graphql", "defineData", "GraphQL.query"],
            "storage_pattern": ["uploadData", "downloadData", "getUrl"],
            "data_pattern": ["a.model", "defineData", "schema"]
        }
        
        for pattern, signatures in pattern_signatures.items():
            if any(sig in content for sig in signatures):
                patterns.append(pattern)
        
        return patterns
    
    def _extract_components_from_content(self, content: str) -> List[str]:
        """Extract UI components from content."""
        components = []
        # Check for common Amplify UI components
        ui_components = ["Authenticator", "StorageImage", "FileUploader", "AccountSettings"]
        
        for component in ui_components:
            if component in content:
                components.append(component)
        
        return components


if __name__ == "__main__":
    # Generate and save index
    indexer = DocumentationIndexer()
    index = indexer.generate_index()
    indexer.save_index()
    indexer.create_summary_table()
    
    # Print overview
    print("\n" + "="*80)
    print(index["overview"])
    print("="*80)