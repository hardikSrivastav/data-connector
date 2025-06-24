"""
General-purpose tools for the LangGraph tool registry system.

These tools are not database-specific and can be used across different
scenarios and database types. All tools implement real functionality
with comprehensive logging and no fallbacks.
"""

import logging
import json
import uuid
import asyncio
import time
import os
import sys
import hashlib
import re
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from pathlib import Path
import traceback

# Configure logging
logger = logging.getLogger(__name__)

class TextProcessingTools:
    """Text processing and manipulation tools."""
    
    @staticmethod
    async def extract_keywords(text: Union[str, List, Dict], max_keywords: int = 10) -> Dict[str, Any]:
        """
        Extract keywords from text using frequency analysis and filtering.
        
        Args:
            text: Text to analyze (string, list, or dict will be converted to string)
            max_keywords: Maximum number of keywords to return
            
        Returns:
            Keywords analysis results
        """
        # Convert input to string if needed
        if isinstance(text, list):
            text = ' '.join(str(item) for item in text)
        elif isinstance(text, dict):
            text = ' '.join(f"{k}: {v}" for k, v in text.items())
        elif not isinstance(text, str):
            text = str(text)
            
        logger.info(f"Extracting keywords from text (length: {len(text)})")
        
        try:
            import string
            from collections import Counter
            
            # Clean and tokenize text
            text_clean = text.lower()
            # Remove punctuation
            text_clean = text_clean.translate(str.maketrans('', '', string.punctuation))
            words = text_clean.split()
            
            # Common stop words to filter out
            stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
                'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their', 'is', 'am', 'are', 'was',
                'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                'could', 'should', 'may', 'might', 'must', 'can', 'shall'
            }
            
            # Filter words
            filtered_words = [word for word in words if len(word) > 2 and word not in stop_words]
            
            # Count word frequencies
            word_counts = Counter(filtered_words)
            
            # Get top keywords
            top_keywords = word_counts.most_common(max_keywords)
            
            # Calculate keyword metrics
            total_words = len(filtered_words)
            keyword_analysis = {
                "keywords": [{"word": word, "count": count, "frequency": count/total_words} 
                           for word, count in top_keywords],
                "total_words": total_words,
                "unique_words": len(word_counts),
                "vocabulary_richness": len(word_counts) / total_words if total_words > 0 else 0,
                "text_length": len(text),
                "avg_word_length": sum(len(word) for word in filtered_words) / len(filtered_words) if filtered_words else 0
            }
            
            logger.info(f"Keyword extraction completed: {len(top_keywords)} keywords found")
            return keyword_analysis
            
        except Exception as e:
            logger.error(f"Failed to extract keywords: {e}")
            raise
    
    @staticmethod
    async def analyze_sentiment(text: Union[str, List, Dict]) -> Dict[str, Any]:
        """
        Analyze sentiment of text using rule-based approach.
        
        Args:
            text: Text to analyze (string, list, or dict will be converted to string)
            
        Returns:
            Sentiment analysis results
        """
        # Convert input to string if needed
        if isinstance(text, list):
            text = ' '.join(str(item) for item in text)
        elif isinstance(text, dict):
            text = ' '.join(f"{k}: {v}" for k, v in text.items())
        elif not isinstance(text, str):
            text = str(text)
            
        logger.info(f"Analyzing sentiment for text (length: {len(text)})")
        
        try:
            # Simple sentiment word lists
            positive_words = {
                'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'awesome', 'brilliant',
                'perfect', 'outstanding', 'superb', 'magnificent', 'marvelous', 'impressive', 'remarkable',
                'exceptional', 'incredible', 'spectacular', 'phenomenal', 'terrific', 'fabulous', 'lovely',
                'beautiful', 'nice', 'pleasant', 'delightful', 'enjoyable', 'satisfying', 'happy', 'pleased',
                'excited', 'thrilled', 'grateful', 'thankful', 'positive', 'optimistic', 'successful'
            }
            
            negative_words = {
                'bad', 'terrible', 'awful', 'horrible', 'disgusting', 'appalling', 'dreadful', 'atrocious',
                'abysmal', 'deplorable', 'disastrous', 'catastrophic', 'tragic', 'devastating', 'shocking',
                'disturbing', 'concerning', 'worrying', 'problematic', 'disappointing', 'frustrating',
                'annoying', 'irritating', 'infuriating', 'outrageous', 'unacceptable', 'wrong', 'failed',
                'broken', 'damaged', 'defective', 'poor', 'weak', 'inadequate', 'insufficient', 'lacking'
            }
            
            # Tokenize and clean text
            import string
            text_clean = text.lower().translate(str.maketrans('', '', string.punctuation))
            words = text_clean.split()
            
            # Count sentiment words
            positive_count = sum(1 for word in words if word in positive_words)
            negative_count = sum(1 for word in words if word in negative_words)
            total_words = len(words)
            
            # Calculate sentiment scores
            positive_score = positive_count / total_words if total_words > 0 else 0
            negative_score = negative_count / total_words if total_words > 0 else 0
            net_sentiment = positive_score - negative_score
            
            # Determine overall sentiment
            if net_sentiment > 0.1:
                overall_sentiment = "positive"
            elif net_sentiment < -0.1:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"
            
            sentiment_analysis = {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": net_sentiment,
                "positive_score": positive_score,
                "negative_score": negative_score,
                "positive_words_found": positive_count,
                "negative_words_found": negative_count,
                "total_words": total_words,
                "confidence": abs(net_sentiment),
                "analysis_method": "rule_based"
            }
            
            logger.info(f"Sentiment analysis completed: {overall_sentiment} (score: {net_sentiment:.3f})")
            return sentiment_analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            raise
    
    @staticmethod
    async def summarize_text(text: str, max_sentences: int = 3) -> Dict[str, Any]:
        """
        Create a summary of text using extractive summarization.
        
        Args:
            text: Text to summarize
            max_sentences: Maximum number of sentences in summary
            
        Returns:
            Text summarization results
        """
        logger.info(f"Summarizing text (length: {len(text)}, max_sentences: {max_sentences})")
        
        try:
            import re
            from collections import Counter
            
            # Split into sentences
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) <= max_sentences:
                return {
                    "summary": text,
                    "original_sentences": len(sentences),
                    "summary_sentences": len(sentences),
                    "compression_ratio": 1.0,
                    "method": "no_compression_needed"
                }
            
            # Score sentences based on word frequency
            # Get word frequencies
            import string
            text_clean = text.lower().translate(str.maketrans('', '', string.punctuation))
            word_freq = Counter(text_clean.split())
            
            # Score each sentence
            sentence_scores = {}
            for i, sentence in enumerate(sentences):
                sentence_clean = sentence.lower().translate(str.maketrans('', '', string.punctuation))
                words = sentence_clean.split()
                score = sum(word_freq[word] for word in words if word in word_freq)
                sentence_scores[i] = score / len(words) if words else 0
            
            # Select top sentences
            top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:max_sentences]
            top_sentences = sorted([idx for idx, score in top_sentences])  # Maintain original order
            
            # Create summary
            summary_sentences = [sentences[idx] for idx in top_sentences]
            summary = '. '.join(summary_sentences) + '.'
            
            summarization_result = {
                "summary": summary,
                "original_sentences": len(sentences),
                "summary_sentences": len(summary_sentences),
                "compression_ratio": len(summary_sentences) / len(sentences),
                "original_length": len(text),
                "summary_length": len(summary),
                "method": "extractive_frequency_based",
                "selected_sentence_indices": top_sentences
            }
            
            logger.info(f"Text summarization completed: {len(summary_sentences)} sentences selected")
            return summarization_result
            
        except Exception as e:
            logger.error(f"Failed to summarize text: {e}")
            raise

class DataValidationTools:
    """Data validation and quality assessment tools."""
    
    @staticmethod
    async def validate_json_structure(json_str: str, expected_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Validate JSON structure and optionally check against a schema.
        
        Args:
            json_str: JSON string to validate
            expected_schema: Optional schema to validate against
            
        Returns:
            Validation results
        """
        logger.info(f"Validating JSON structure (length: {len(json_str)})")
        
        try:
            validation_result = {
                "is_valid_json": False,
                "parsed_data": None,
                "schema_valid": None,
                "errors": [],
                "warnings": [],
                "data_types": {},
                "structure_info": {}
            }
            
            # Try to parse JSON
            try:
                parsed_data = json.loads(json_str)
                validation_result["is_valid_json"] = True
                validation_result["parsed_data"] = parsed_data
                logger.debug("JSON parsing successful")
                
                # Analyze structure
                validation_result["structure_info"] = DataValidationTools._analyze_json_structure(parsed_data)
                
                # Validate against schema if provided
                if expected_schema:
                    schema_validation = DataValidationTools._validate_against_schema(parsed_data, expected_schema)
                    validation_result.update(schema_validation)
                
            except json.JSONDecodeError as e:
                validation_result["errors"].append(f"JSON parsing error: {str(e)}")
                logger.warning(f"JSON parsing failed: {e}")
            
            logger.info(f"JSON validation completed: {'valid' if validation_result['is_valid_json'] else 'invalid'}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to validate JSON: {e}")
            raise
    
    @staticmethod
    def _analyze_json_structure(data: Any, path: str = "root") -> Dict[str, Any]:
        """Analyze the structure of JSON data."""
        if isinstance(data, dict):
            return {
                "type": "object",
                "keys": list(data.keys()),
                "key_count": len(data),
                "nested_structure": {k: DataValidationTools._analyze_json_structure(v, f"{path}.{k}") 
                                   for k, v in data.items()}
            }
        elif isinstance(data, list):
            return {
                "type": "array",
                "length": len(data),
                "element_types": list(set(type(item).__name__ for item in data)),
                "sample_structure": DataValidationTools._analyze_json_structure(data[0], f"{path}[0]") if data else None
            }
        else:
            return {
                "type": type(data).__name__,
                "value": data if not isinstance(data, str) or len(str(data)) < 100 else f"{str(data)[:100]}..."
            }
    
    @staticmethod
    def _validate_against_schema(data: Any, schema: Dict) -> Dict[str, Any]:
        """Basic schema validation."""
        errors = []
        warnings = []
        
        # Simple schema validation (can be extended)
        if "type" in schema:
            expected_type = schema["type"]
            actual_type = type(data).__name__
            
            if expected_type == "object" and not isinstance(data, dict):
                errors.append(f"Expected object, got {actual_type}")
            elif expected_type == "array" and not isinstance(data, list):
                errors.append(f"Expected array, got {actual_type}")
        
        if "required" in schema and isinstance(data, dict):
            required_fields = schema["required"]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                errors.append(f"Missing required fields: {missing_fields}")
        
        return {
            "schema_valid": len(errors) == 0,
            "schema_errors": errors,
            "schema_warnings": warnings
        }
    
    @staticmethod
    async def check_data_quality(data: List[Dict], quality_checks: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Assess data quality across multiple dimensions.
        
        Args:
            data: List of data records to analyze
            quality_checks: Optional specific quality checks to perform
            
        Returns:
            Data quality assessment results
        """
        logger.info(f"Checking data quality for {len(data)} records")
        
        try:
            quality_result = {
                "total_records": len(data),
                "completeness": {},
                "consistency": {},
                "validity": {},
                "uniqueness": {},
                "overall_score": 0.0,
                "recommendations": []
            }
            
            if not data:
                quality_result["recommendations"].append("No data to analyze")
                return quality_result
            
            # Analyze completeness
            all_fields = set()
            for record in data:
                if isinstance(record, dict):
                    all_fields.update(record.keys())
            
            field_completeness = {}
            for field in all_fields:
                non_null_count = sum(1 for record in data 
                                   if isinstance(record, dict) and 
                                   field in record and 
                                   record[field] is not None and 
                                   record[field] != "")
                field_completeness[field] = non_null_count / len(data)
            
            quality_result["completeness"] = {
                "field_completeness": field_completeness,
                "avg_completeness": sum(field_completeness.values()) / len(field_completeness) if field_completeness else 0
            }
            
            # Analyze consistency (data types)
            field_types = {}
            for field in all_fields:
                types_found = set()
                for record in data:
                    if isinstance(record, dict) and field in record and record[field] is not None:
                        types_found.add(type(record[field]).__name__)
                field_types[field] = list(types_found)
            
            inconsistent_fields = {field: types for field, types in field_types.items() if len(types) > 1}
            
            quality_result["consistency"] = {
                "field_types": field_types,
                "inconsistent_fields": inconsistent_fields,
                "consistency_score": 1 - (len(inconsistent_fields) / len(all_fields)) if all_fields else 1
            }
            
            # Analyze uniqueness (for records with id field)
            id_fields = ["id", "ID", "_id", "uuid", "key"]
            unique_analysis = {}
            
            for id_field in id_fields:
                if id_field in all_fields:
                    id_values = [record.get(id_field) for record in data 
                               if isinstance(record, dict) and record.get(id_field) is not None]
                    unique_analysis[id_field] = {
                        "total_values": len(id_values),
                        "unique_values": len(set(id_values)),
                        "uniqueness_ratio": len(set(id_values)) / len(id_values) if id_values else 0
                    }
            
            quality_result["uniqueness"] = unique_analysis
            
            # Calculate overall quality score
            completeness_score = quality_result["completeness"]["avg_completeness"]
            consistency_score = quality_result["consistency"]["consistency_score"]
            uniqueness_score = max([analysis["uniqueness_ratio"] for analysis in unique_analysis.values()], default=1.0)
            
            quality_result["overall_score"] = (completeness_score + consistency_score + uniqueness_score) / 3
            
            # Generate recommendations
            if completeness_score < 0.8:
                quality_result["recommendations"].append("Low data completeness detected, consider data cleaning")
            
            if inconsistent_fields:
                quality_result["recommendations"].append(f"Inconsistent data types in fields: {list(inconsistent_fields.keys())}")
            
            if uniqueness_score < 0.95:
                quality_result["recommendations"].append("Potential duplicate records detected")
            
            logger.info(f"Data quality analysis completed: overall score {quality_result['overall_score']:.2f}")
            return quality_result
            
        except Exception as e:
            logger.error(f"Failed to check data quality: {e}")
            raise

class FileSystemTools:
    """File system and data export tools."""
    
    @staticmethod
    async def export_data_to_csv(data: List[Dict], filepath: str, include_headers: bool = True) -> Dict[str, Any]:
        """
        Export data to CSV file.
        
        Args:
            data: List of dictionaries to export
            filepath: Path to save CSV file
            include_headers: Whether to include headers
            
        Returns:
            Export operation results
        """
        logger.info(f"Exporting {len(data)} records to CSV: {filepath}")
        
        try:
            import csv
            
            if not data:
                logger.warning("No data to export")
                return {"success": False, "error": "No data provided"}
            
            # Get all unique field names
            all_fields = set()
            for record in data:
                if isinstance(record, dict):
                    all_fields.update(record.keys())
            
            fieldnames = sorted(list(all_fields))
            
            # Create directory if it doesn't exist
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Write CSV file
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if include_headers:
                    writer.writeheader()
                
                for record in data:
                    if isinstance(record, dict):
                        # Fill missing fields with empty strings
                        row = {field: record.get(field, '') for field in fieldnames}
                        writer.writerow(row)
            
            # Get file info
            file_stat = os.stat(filepath)
            
            export_result = {
                "success": True,
                "filepath": filepath,
                "records_exported": len(data),
                "fields_exported": len(fieldnames),
                "file_size_bytes": file_stat.st_size,
                "export_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"CSV export completed: {export_result['records_exported']} records, {export_result['file_size_bytes']} bytes")
            return export_result
            
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            raise
    
    @staticmethod
    async def export_data_to_json(data: Any, filepath: str, pretty_print: bool = True) -> Dict[str, Any]:
        """
        Export data to JSON file.
        
        Args:
            data: Data to export
            filepath: Path to save JSON file
            pretty_print: Whether to format JSON for readability
            
        Returns:
            Export operation results
        """
        logger.info(f"Exporting data to JSON: {filepath}")
        
        try:
            # Create directory if it doesn't exist
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Write JSON file
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                if pretty_print:
                    json.dump(data, jsonfile, indent=2, ensure_ascii=False, default=str)
                else:
                    json.dump(data, jsonfile, ensure_ascii=False, default=str)
            
            # Get file info
            file_stat = os.stat(filepath)
            
            export_result = {
                "success": True,
                "filepath": filepath,
                "file_size_bytes": file_stat.st_size,
                "export_timestamp": datetime.now().isoformat(),
                "pretty_print": pretty_print
            }
            
            logger.info(f"JSON export completed: {export_result['file_size_bytes']} bytes")
            return export_result
            
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")
            raise

class UtilityTools:
    """General utility and helper tools."""
    
    @staticmethod
    async def generate_unique_id(prefix: str = "", length: int = 8) -> str:
        """
        Generate a unique identifier.
        
        Args:
            prefix: Optional prefix for the ID
            length: Length of the random part
            
        Returns:
            Unique identifier string
        """
        logger.debug(f"Generating unique ID with prefix: {prefix}, length: {length}")
        
        try:
            import random
            import string
            
            # Generate random string
            random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
            
            # Combine with timestamp for uniqueness
            timestamp = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp
            
            unique_id = f"{prefix}{timestamp}_{random_part}" if prefix else f"{timestamp}_{random_part}"
            
            logger.debug(f"Generated unique ID: {unique_id}")
            return unique_id
            
        except Exception as e:
            logger.error(f"Failed to generate unique ID: {e}")
            raise
    
    @staticmethod
    async def calculate_hash(data: Any, algorithm: str = "md5") -> str:
        """
        Calculate hash of data.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm to use
            
        Returns:
            Hash string
        """
        logger.debug(f"Calculating {algorithm} hash")
        
        try:
            # Convert data to string
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, sort_keys=True, default=str)
            else:
                data_str = str(data)
            
            # Calculate hash
            if algorithm.lower() == "md5":
                hash_obj = hashlib.md5(data_str.encode('utf-8'))
            elif algorithm.lower() == "sha1":
                hash_obj = hashlib.sha1(data_str.encode('utf-8'))
            elif algorithm.lower() == "sha256":
                hash_obj = hashlib.sha256(data_str.encode('utf-8'))
            else:
                raise ValueError(f"Unsupported hash algorithm: {algorithm}")
            
            hash_value = hash_obj.hexdigest()
            logger.debug(f"Hash calculated: {hash_value}")
            return hash_value
            
        except Exception as e:
            logger.error(f"Failed to calculate hash: {e}")
            raise
    
    @staticmethod
    async def format_timestamp(timestamp: Optional[Union[int, float, str]] = None, 
                              format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        Format timestamp to human-readable string.
        
        Args:
            timestamp: Timestamp to format (defaults to current time)
            format_str: Format string for datetime formatting
            
        Returns:
            Formatted timestamp string
        """
        logger.debug(f"Formatting timestamp: {timestamp}")
        
        try:
            if timestamp is None:
                dt = datetime.now()
            elif isinstance(timestamp, (int, float)):
                # Assume Unix timestamp
                if timestamp > 1e10:  # Milliseconds
                    timestamp = timestamp / 1000
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                # Try to parse string timestamp
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    # Try Unix timestamp as string
                    dt = datetime.fromtimestamp(float(timestamp))
            else:
                raise ValueError(f"Unsupported timestamp type: {type(timestamp)}")
            
            formatted = dt.strftime(format_str)
            logger.debug(f"Formatted timestamp: {formatted}")
            return formatted
            
        except Exception as e:
            logger.error(f"Failed to format timestamp: {e}")
            raise 