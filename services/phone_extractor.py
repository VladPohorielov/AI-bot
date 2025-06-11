"""
Phone Number Extraction Service
Extracts and formats Ukrainian and international phone numbers from text
"""
import re
from typing import List, Dict, Set
from dataclasses import dataclass


@dataclass
class PhoneNumber:
    """Represents an extracted phone number"""
    raw: str              # Original text as found
    formatted: str        # Standardized format
    country: str          # Country code (UA, etc.)
    type: str            # mobile, landline, etc.
    confidence: float    # Extraction confidence 0-1


class PhoneExtractor:
    """Service for extracting phone numbers from conversation text"""
    
    # Ukrainian phone patterns
    UA_PATTERNS = [
        # International format: +380XXXXXXXXX
        (r'\+380\s*(\d{2})\s*(\d{3})\s*(\d{2})\s*(\d{2})', 'international'),
        
        # National format: 0XXXXXXXXX  
        (r'\b0(\d{2})\s*(\d{3})\s*(\d{2})\s*(\d{2})\b', 'national'),
        
        # With country code but no +: 380XXXXXXXXX
        (r'\b380\s*(\d{2})\s*(\d{3})\s*(\d{2})\s*(\d{2})\b', 'country_code'),
        
        # Formatted variants with dashes/dots
        (r'\+380[\-\.\s]*(\d{2})[\-\.\s]*(\d{3})[\-\.\s]*(\d{2})[\-\.\s]*(\d{2})', 'international_formatted'),
        (r'\b0(\d{2})[\-\.\s]*(\d{3})[\-\.\s]*(\d{2})[\-\.\s]*(\d{2})\b', 'national_formatted'),
        
        # Parentheses format: +380 (XX) XXX-XX-XX
        (r'\+380\s*\(\s*(\d{2})\s*\)\s*(\d{3})[\-\s]*(\d{2})[\-\s]*(\d{2})', 'parentheses'),
        (r'\b0\(\s*(\d{2})\s*\)\s*(\d{3})[\-\s]*(\d{2})[\-\s]*(\d{2})\b', 'national_parentheses'),
        
        # Kyiv landline: +380 44 XXX-XX-XX, 044-XXX-XX-XX
        (r'\+380\s*44\s*(\d{3})[\-\s]*(\d{2})[\-\s]*(\d{2})', 'kyiv_landline'),
        (r'\b044[\-\s]*(\d{3})[\-\s]*(\d{2})[\-\s]*(\d{2})\b', 'kyiv_landline_short'),
    ]
    
    # International patterns
    INTL_PATTERNS = [
        # Generic international: +XX XXXXXXXXX
        (r'\+(\d{1,3})\s*(\d{3,12})', 'international_generic'),
        
        # US format: +1 XXX XXX XXXX
        (r'\+1\s*(\d{3})\s*(\d{3})\s*(\d{4})', 'us_format'),
        
        # European formats
        (r'\+49\s*(\d{3,11})', 'germany'),
        (r'\+33\s*(\d{9})', 'france'),
        (r'\+44\s*(\d{10})', 'uk'),
    ]
    
    def __init__(self):
        self.all_patterns = self.UA_PATTERNS + self.INTL_PATTERNS
    
    def extract_phones(self, text: str) -> List[PhoneNumber]:
        """
        Extract all phone numbers from text
        Returns list of PhoneNumber objects sorted by confidence
        """
        found_phones = []
        processed_positions = set()
        
        for pattern, pattern_type in self.all_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                start, end = match.span()
                
                # Skip if this position already processed by higher priority pattern
                if any(pos in range(start, end) for pos in processed_positions):
                    continue
                
                # Mark this position as processed
                processed_positions.update(range(start, end))
                
                # Extract and format phone
                phone = self._process_match(match, pattern_type)
                if phone and self._validate_phone(phone):
                    found_phones.append(phone)
        
        # Sort by confidence (highest first) and remove duplicates
        found_phones = self._deduplicate_phones(found_phones)
        return sorted(found_phones, key=lambda p: p.confidence, reverse=True)
    
    def _process_match(self, match: re.Match, pattern_type: str) -> PhoneNumber:
        """Process regex match into PhoneNumber object"""
        raw_text = match.group(0)
        groups = match.groups()
        
        # Format based on pattern type
        if pattern_type.startswith('international'):
            formatted = self._format_international(groups, pattern_type)
            # Extract country code safely
            if groups and len(groups) > 0:
                # For Ukrainian patterns, first group might be operator code
                if pattern_type == 'international':
                    country_code = "380"  # Ukrainian international format
                else:
                    country_code = str(groups[0])
            else:
                country_code = "380"
            country = self._detect_country(country_code)
            confidence = 0.9
            
        elif pattern_type.startswith('national'):
            formatted = self._format_ukrainian_national(groups)
            country = "UA"
            confidence = 0.8
            
        elif pattern_type.startswith('kyiv'):
            formatted = self._format_kyiv_landline(groups)
            country = "UA"
            confidence = 0.7
            
        else:
            formatted = self._format_generic(raw_text)
            country = "Unknown"
            confidence = 0.5
        
        phone_type = self._detect_phone_type(formatted)
        
        return PhoneNumber(
            raw=raw_text.strip(),
            formatted=formatted,
            country=country,
            type=phone_type,
            confidence=confidence
        )
    
    def _format_international(self, groups: tuple, pattern_type: str) -> str:
        """Format international phone number"""
        if not groups:
            return ""
            
        if pattern_type.startswith('international') and len(groups) >= 4:
            # +380 XX XXX XX XX
            return f"+380 {groups[0]} {groups[1]} {groups[2]} {groups[3]}"
        
        # Generic international
        return f"+{groups[0]} {groups[1]}" if len(groups) >= 2 else f"+{groups[0]}"
    
    def _format_ukrainian_national(self, groups: tuple) -> str:
        """Format Ukrainian national number to international"""
        if len(groups) >= 4:
            return f"+380 {groups[0]} {groups[1]} {groups[2]} {groups[3]}"
        return "+380 " + " ".join(groups)
    
    def _format_kyiv_landline(self, groups: tuple) -> str:
        """Format Kyiv landline number"""
        if len(groups) >= 3:
            return f"+380 44 {groups[0]} {groups[1]} {groups[2]}"
        return "+380 44 " + " ".join(groups)
    
    def _format_generic(self, raw_text: str) -> str:
        """Generic formatting for unrecognized patterns"""
        # Clean and basic formatting
        cleaned = re.sub(r'[^\d+]', '', raw_text)
        return cleaned
    
    def _detect_country(self, country_code: str) -> str:
        """Detect country from country code"""
        country_map = {
            "380": "UA",
            "1": "US",
            "44": "UK", 
            "49": "DE",
            "33": "FR",
            "7": "RU"
        }
        return country_map.get(country_code, "Unknown")
    
    def _detect_phone_type(self, formatted: str) -> str:
        """Detect if mobile, landline, etc."""
        if "+380" in formatted:
            # Ukrainian mobile operators
            mobile_prefixes = ["50", "63", "66", "67", "68", "91", "92", "93", "94", "95", "96", "97", "98", "99"]
            for prefix in mobile_prefixes:
                if f" {prefix} " in formatted:
                    return "mobile"
            
            # Kyiv landline
            if " 44 " in formatted:
                return "landline"
                
            return "unknown"
        
        return "international"
    
    def _validate_phone(self, phone: PhoneNumber) -> bool:
        """Validate extracted phone number"""
        if not phone.formatted:
            return False
            
        # Check minimum length
        digits_only = re.sub(r'[^\d]', '', phone.formatted)
        if len(digits_only) < 7:
            return False
            
        # Ukrainian specific validation
        if phone.country == "UA":
            if not (len(digits_only) == 12 and digits_only.startswith("380")):
                return False
        
        return True
    
    def _deduplicate_phones(self, phones: List[PhoneNumber]) -> List[PhoneNumber]:
        """Remove duplicate phone numbers, keeping the highest confidence one"""
        seen_formatted = {}
        
        for phone in phones:
            normalized = re.sub(r'[^\d]', '', phone.formatted)
            
            if normalized not in seen_formatted or phone.confidence > seen_formatted[normalized].confidence:
                seen_formatted[normalized] = phone
        
        return list(seen_formatted.values())
    
    def format_for_display(self, phones: List[PhoneNumber]) -> str:
        """Format phone numbers for display in bot messages"""
        if not phones:
            return ""
        
        result = "📞 **ТЕЛЕФОНИ:**\n"
        for phone in phones:
            flag = "🇺🇦" if phone.country == "UA" else "🌍"
            type_emoji = "📱" if phone.type == "mobile" else "☎️" if phone.type == "landline" else "📞"
            
            result += f"• {flag} {type_emoji} {phone.formatted}"
            if phone.confidence < 0.7:
                result += " ❓"  # Low confidence indicator
            result += "\n"
        
        return result


# Global instance
phone_extractor = PhoneExtractor() 