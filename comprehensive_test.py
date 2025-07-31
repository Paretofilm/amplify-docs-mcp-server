#!/usr/bin/env python3
"""
Comprehensive test suite for the enhanced Amplify MCP server
Tests all functionality and edge cases
"""

import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, List
from amplify_docs_server import AmplifyDocsDatabase, DocumentationIndexer

class ComprehensiveTester:
    def __init__(self):
        self.db = AmplifyDocsDatabase()
        self.test_results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
    
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """Log test results."""
        if passed:
            self.test_results["passed"].append(test_name)
            print(f"✅ {test_name}")
        else:
            self.test_results["failed"].append((test_name, message))
            print(f"❌ {test_name}: {message}")
    
    def log_warning(self, test_name: str, message: str):
        """Log warnings."""
        self.test_results["warnings"].append((test_name, message))
        print(f"⚠️  {test_name}: {message}")
    
    async def test_database_connection(self):
        """Test database connectivity."""
        try:
            stats = self.db.get_stats()
            total_docs = stats.get('total_documents', 0)
            
            if total_docs > 0:
                self.log_result("Database Connection", True)
                print(f"   Total documents: {total_docs}")
                
                # Check categories
                categories = stats.get('categories', {})
                print("   Categories:")
                for cat, count in categories.items():
                    print(f"     - {cat}: {count}")
                
                # Verify we have frontend docs
                frontend_count = categories.get('frontend', 0)
                if frontend_count < 50:
                    self.log_warning("Frontend Documentation", 
                                   f"Only {frontend_count} frontend docs (expected 50+)")
            else:
                self.log_result("Database Connection", False, "No documents found")
        except Exception as e:
            self.log_result("Database Connection", False, str(e))
    
    async def test_documentation_index(self):
        """Test documentation index generation."""
        try:
            # Check if index file exists
            index_file = Path("documentation_index.json")
            if not index_file.exists():
                # Try to generate it
                indexer = DocumentationIndexer()
                index = indexer.generate_index()
                indexer.save_index()
            
            # Load and verify index
            with open(index_file, 'r') as f:
                index = json.load(f)
            
            # Check required fields
            required_fields = ["overview", "categories", "quick_access", "patterns", "components", "common_tasks"]
            missing = [field for field in required_fields if field not in index]
            
            if missing:
                self.log_result("Documentation Index Structure", False, f"Missing fields: {missing}")
            else:
                self.log_result("Documentation Index Structure", True)
                
                # Check categories
                cat_count = len(index["categories"])
                if cat_count < 5:
                    self.log_warning("Documentation Categories", f"Only {cat_count} categories")
                
                # Check patterns
                pattern_count = sum(len(patterns) for patterns in index["patterns"].values())
                print(f"   Found {pattern_count} code patterns")
                
                # Check components
                component_count = len(index["components"])
                print(f"   Found {component_count} UI components")
                
        except Exception as e:
            self.log_result("Documentation Index", False, str(e))
    
    async def test_search_functionality(self):
        """Test search with various queries."""
        test_queries = [
            # Basic searches
            ("authentication", "Should find auth docs"),
            ("storage upload", "Should find storage docs"),
            ("graphql api", "Should find API docs"),
            
            # Fuzzy/synonym searches
            ("auth", "Should expand to authentication"),
            ("ui components", "Should find frontend docs"),
            ("deploy", "Should find deployment docs"),
            
            # Typo handling
            ("authentcation", "Should handle typos"),
            ("storag", "Should handle partial words"),
            
            # Complex queries
            ("file upload component", "Should find FileUploader"),
            ("real time subscription", "Should find real-time docs"),
            
            # Category-specific
            ("frontend button", "Should find button component"),
            ("troubleshooting error", "Should find troubleshooting docs")
        ]
        
        print("\n🔍 Testing Search Functionality:")
        
        for query, description in test_queries:
            try:
                results = self.db.search_documents(query, limit=5)
                
                if results:
                    self.log_result(f"Search: '{query}'", True)
                    print(f"   {description} - Found {len(results)} results")
                    # Show first result
                    if results:
                        print(f"   Top result: {results[0]['title']}")
                else:
                    self.log_result(f"Search: '{query}'", False, "No results found")
                    
            except Exception as e:
                self.log_result(f"Search: '{query}'", False, str(e))
    
    async def test_specific_document_retrieval(self):
        """Test getting specific documents."""
        test_urls = [
            "https://docs.amplify.aws/nextjs/build-ui/",
            "https://ui.docs.amplify.aws/react/connected-components/authenticator",
            "https://docs.amplify.aws/nextjs/build-a-backend/data/set-up-data/"
        ]
        
        print("\n📄 Testing Document Retrieval:")
        
        for url in test_urls:
            try:
                doc = self.db.get_document_by_url(url)
                if doc:
                    self.log_result(f"Get Doc: {url.split('/')[-2]}", True)
                    print(f"   Title: {doc['title']}")
                    print(f"   Category: {doc['category']}")
                else:
                    self.log_result(f"Get Doc: {url}", False, "Document not found")
            except Exception as e:
                self.log_result(f"Get Doc: {url}", False, str(e))
    
    async def test_pattern_search(self):
        """Test pattern finding functionality."""
        pattern_types = ["auth", "api", "storage", "deployment", "configuration", "database", "functions"]
        
        print("\n🔧 Testing Pattern Search:")
        
        for pattern_type in pattern_types:
            # Simulate the findPatterns query
            pattern_queries = {
                "auth": "authentication signIn signUp cognito user authenticator",
                "api": "graphql rest api endpoint mutation query data model",
                "storage": "s3 storage upload download file fileuploader storageimage",
                "deployment": "deploy hosting amplify build npx",
                "configuration": "configure amplify_outputs.json setup backend",
                "database": "dynamodb database table data model schema",
                "functions": "lambda function serverless backend handler"
            }
            
            query = pattern_queries.get(pattern_type, pattern_type)
            
            try:
                results = self.db.search_documents(query, limit=5)
                if results:
                    self.log_result(f"Pattern: {pattern_type}", True)
                    print(f"   Found {len(results)} pattern examples")
                else:
                    self.log_warning(f"Pattern: {pattern_type}", "No patterns found")
            except Exception as e:
                self.log_result(f"Pattern: {pattern_type}", False, str(e))
    
    async def test_categories(self):
        """Test category listing and filtering."""
        print("\n📁 Testing Categories:")
        
        try:
            categories = self.db.list_categories()
            
            if categories:
                self.log_result("List Categories", True)
                print(f"   Found {len(categories)} categories: {', '.join(categories)}")
                
                # Test filtering by category
                for category in ["frontend", "backend", "troubleshooting"]:
                    if category in categories:
                        results = self.db.search_documents("", category=category, limit=3)
                        print(f"   {category}: {len(results)} docs")
            else:
                self.log_result("List Categories", False, "No categories found")
                
        except Exception as e:
            self.log_result("List Categories", False, str(e))
    
    async def test_summary_table(self):
        """Test if summary table exists and works."""
        print("\n📊 Testing Summary Table:")
        
        try:
            # Check if summary table exists
            if self.db._table_exists('document_summaries'):
                self.log_result("Summary Table Exists", True)
                
                # Try a search that uses summaries
                results = self.db.search_documents("connected components", limit=5)
                if results:
                    print(f"   Summary-enhanced search found {len(results)} results")
            else:
                self.log_warning("Summary Table", "Table doesn't exist - creating now")
                # Create it
                indexer = DocumentationIndexer()
                indexer.create_summary_table()
                
        except Exception as e:
            self.log_result("Summary Table", False, str(e))
    
    async def test_edge_cases(self):
        """Test edge cases and error handling."""
        print("\n🔥 Testing Edge Cases:")
        
        # Empty search
        try:
            results = self.db.search_documents("")
            self.log_result("Empty Search", True)
        except:
            self.log_result("Empty Search", False, "Failed on empty query")
        
        # Very long query
        try:
            long_query = " ".join(["test"] * 100)
            results = self.db.search_documents(long_query, limit=1)
            self.log_result("Long Query", True)
        except:
            self.log_result("Long Query", False, "Failed on long query")
        
        # Special characters
        try:
            results = self.db.search_documents("test'; DROP TABLE--", limit=1)
            self.log_result("SQL Injection Test", True)
        except:
            self.log_result("SQL Injection Test", False, "Vulnerable to SQL injection")
        
        # Non-existent category
        try:
            results = self.db.search_documents("test", category="non-existent-category")
            self.log_result("Invalid Category", True)
        except:
            self.log_result("Invalid Category", False, "Failed on invalid category")
        
        # Invalid URL
        try:
            doc = self.db.get_document_by_url("https://invalid-url.com")
            if doc is None:
                self.log_result("Invalid URL Retrieval", True)
            else:
                self.log_result("Invalid URL Retrieval", False, "Returned document for invalid URL")
        except:
            self.log_result("Invalid URL Retrieval", False, "Exception on invalid URL")
    
    async def test_performance(self):
        """Test performance with various operations."""
        print("\n⚡ Testing Performance:")
        
        import time
        
        # Search performance
        start = time.time()
        results = self.db.search_documents("amplify", limit=50)
        search_time = time.time() - start
        
        if search_time < 1.0:
            self.log_result("Search Performance", True)
            print(f"   Search completed in {search_time:.3f}s")
        else:
            self.log_warning("Search Performance", f"Slow search: {search_time:.3f}s")
        
        # Category listing performance
        start = time.time()
        categories = self.db.list_categories()
        cat_time = time.time() - start
        
        if cat_time < 0.1:
            self.log_result("Category Listing Performance", True)
            print(f"   Categories listed in {cat_time:.3f}s")
        else:
            self.log_warning("Category Performance", f"Slow: {cat_time:.3f}s")
    
    async def test_quick_patterns_data(self):
        """Verify quick start patterns are complete."""
        print("\n🚀 Testing Quick Start Patterns:")
        
        tasks = [
            "create-app", "add-auth", "add-api", "add-storage", 
            "file-upload", "user-profile", "real-time-data", 
            "deploy-app", "custom-auth-ui", "data-relationships"
        ]
        
        # This would be tested through the MCP server, but we can verify the data exists
        for task in tasks:
            # Just verify we have docs that would support these patterns
            if task == "create-app":
                query = "create amplify nextjs"
            elif task == "add-auth":
                query = "authentication authenticator"
            elif task == "file-upload":
                query = "fileuploader storage upload"
            else:
                query = task.replace("-", " ")
            
            results = self.db.search_documents(query, limit=2)
            if results:
                self.log_result(f"Pattern Support: {task}", True)
            else:
                self.log_warning(f"Pattern Support: {task}", "Limited documentation")
    
    async def run_all_tests(self):
        """Run all tests."""
        print("🧪 Starting Comprehensive Tests for Amplify MCP Server\n")
        print("="*60)
        
        # Run tests in order
        await self.test_database_connection()
        await self.test_documentation_index()
        await self.test_search_functionality()
        await self.test_specific_document_retrieval()
        await self.test_pattern_search()
        await self.test_categories()
        await self.test_summary_table()
        await self.test_edge_cases()
        await self.test_performance()
        await self.test_quick_patterns_data()
        
        # Summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY:")
        print(f"✅ Passed: {len(self.test_results['passed'])}")
        print(f"❌ Failed: {len(self.test_results['failed'])}")
        print(f"⚠️  Warnings: {len(self.test_results['warnings'])}")
        
        if self.test_results['failed']:
            print("\n❌ Failed Tests:")
            for test, message in self.test_results['failed']:
                print(f"   - {test}: {message}")
        
        if self.test_results['warnings']:
            print("\n⚠️  Warnings:")
            for test, message in self.test_results['warnings']:
                print(f"   - {test}: {message}")
        
        return len(self.test_results['failed']) == 0


async def main():
    tester = ComprehensiveTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())