import os
import json
import logging
import random
from typing import Dict, List, Tuple
import aiohttp
from emotional_guidance import get_emotional_guidance

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

async def generate_response(
    character: Dict, 
    conversation_history: List[Dict], 
    character_stats: Dict
) -> Tuple[str, float]:
    """
    Generate a response from the character using Mistral AI
    
    Args:
        character: The character data
        conversation_history: The conversation history
        character_stats: The character's mood and personality stats
    
    Returns:
        Tuple of (response text, mood change)
    """
    # Get the Mistral API key from environment variable
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable not set!")
    
    # Prepare the system prompt with character info and current stats
    system_prompt = _prepare_system_prompt(character, character_stats)
    
    # Prepare the messages for the Mistral API
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add the conversation history
    for message in conversation_history:
        messages.append({"role": message["role"], "content": message["content"]})
    
    # Check if the user has NSFW mode enabled
    # This comes from character_stats which contains the user_nsfw_preference field
    nsfw_mode = character_stats.get("user_nsfw_preference", False)
    
    # Prepare the request payload
    payload = {
        "model": "mistral-medium",  # Using Mistral Medium model
        "messages": messages,
        "temperature": 0.7,  # A moderate temperature for good creativity but consistent responses
        "max_tokens": 400,  # Limit response length for shorter replies
        "top_p": 0.9,
        "safe_prompt": not nsfw_mode  # Enable safety filters only if NSFW mode is disabled
    }
    
    # Make the API call with better error handling
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            async with session.post(MISTRAL_API_URL, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Mistral API error: Status {response.status} - {error_text}")
                    
                    # More descriptive error based on status code
                    if response.status == 401:
                        raise ValueError("Authentication error: Invalid API key or unauthorized access.")
                    elif response.status == 400:
                        raise ValueError(f"Bad request to Mistral API: {error_text}")
                    elif response.status == 429:
                        raise ValueError("Rate limit exceeded with Mistral API. Please try again later.")
                    elif response.status >= 500:
                        raise ValueError("Mistral API server error. Please try again later.")
                    else:
                        raise ValueError(f"Mistral API error: {response.status} - {error_text}")
                
                response_data = await response.json()
                
                # Extract the response text with safe access
                if (not response_data.get("choices") or 
                    len(response_data["choices"]) == 0 or
                    not response_data["choices"][0].get("message") or
                    not response_data["choices"][0]["message"].get("content")):
                    
                    logger.error(f"Malformed response from Mistral API: {json.dumps(response_data)}")
                    raise ValueError("Received invalid response format from Mistral API")
                
                response_text = response_data["choices"][0]["message"]["content"]
    except aiohttp.ClientError as e:
        logger.error(f"Network error when connecting to Mistral API: {str(e)}")
        raise ValueError(f"Connection error with Mistral API: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from Mistral API: {str(e)}")
        raise ValueError("Received invalid JSON response from Mistral API")
    
    # Filter out AI disclaimers and meta-commentary
    import re
    disclaimer_patterns = [
        # Model disclaimers
        r'\(Note:.*?\)',
        r'\(At this point.*?\)',
        r'Please note that I am an AI.*?\.', 
        r'I am an AI.*?\.', 
        r'As an AI.*?\.', 
        r'I do not have.*?emotions.*?\.', 
        r'I cannot.*?feel.*?\.', 
        r'I\'m just a.*?model.*?\.',
        r'I don\'t have.*?feelings.*?\.',
        
        # Meta-commentary in parentheses - catch all possible patterns
        r'\([^)]*instructions?\)|\([^)]*per [^)]*instructions?\)', 
        r'\(My.*?remain.*?\)',
        r'\(Also,.*?\)',
        r'\(I [^)]*acknowledged.*?\)',
        r'\(I [^)]*respond.*?\)',
        r'\(I [^)]*express.*?\)',
        r'\(I [^)]*follow.*?\)',
        r'\([^)]*your character[^)]*\)',
        r'\([^)]*emotion.*?\)',
        r'\([^)]*relationship.*?\)',
        r'\([^)]*user[^)]*\)',
        r'\([^)]*model[^)]*\)',
        r'\([^)]*note[^)]*\)',
        r'\([^)]*As per[^)]*\)',
        r'\([^)]*In line with[^)]*\)',
        r'\([^)]*maintain[^)]*\)',
        r'\([^)]*keeping[^)]*\)',
        r'\([^)]*continuing[^)]*\)',
        r'\([^)]*based on[^)]*\)',
        
        # Square bracket notes and metadata
        r'\[Note:.*?\]',
        r'\[note:.*?\]',
        r'\[Note .*?\]',
        r'\[note .*?\]',
        r'\[OOC:.*?\]',
        r'\[Character\'s .*?\]',
        r'\[Character .*?\]',
        r'\[.*?mood.*?\]',
        r'\[.*?attitude.*?\]',
        r'\[.*?thinking.*?\]',
        r'\[.*?feeling.*?\]',
        r'\[.*?emotion.*?\]',
        r'\[.*?state.*?\]',
        r'\[.*?tone.*?\]',
        r'\[.*?expression.*?\]',
        r'\[.*?posture.*?\]',
        r'\[.*?remains.*?\]'
    ]
    
    # Also remove character name prefixes like "Naruto:"
    character_name = character.get("name", "")
    if character_name:
        # Escape any special regex characters in the name
        escaped_name = re.escape(character_name)
        # Add pattern to remove character name prefix, whether at start of text or after newlines
        disclaimer_patterns.append(f"(^|\\n+){escaped_name}\\s*:")
        # Also try with just first name if there's a space in the name
        if " " in character_name:
            first_name = character_name.split(" ")[0]
            escaped_first_name = re.escape(first_name)
            disclaimer_patterns.append(f"(^|\\n+){escaped_first_name}\\s*:")
    
    # Apply all patterns to remove disclaimers
    for pattern in disclaimer_patterns:
        # For character name patterns (which can match with newlines), replace with captured group
        if pattern.startswith("(^|\\n+)"):
            response_text = re.sub(pattern, r'\1', response_text, flags=re.IGNORECASE | re.DOTALL)
        else:
            # For other patterns, just remove them
            response_text = re.sub(pattern, '', response_text, flags=re.IGNORECASE | re.DOTALL)
        
    # Clean up any awkward spacing left by removals
    response_text = re.sub(r'\n\s*\n\s*\n', '\n\n', response_text)
    # Clean up any potential empty lines at the beginning
    response_text = re.sub(r'^\n+', '', response_text)
    response_text = response_text.strip()
    
    # Enhanced emotion detection and mood change calculation
    # First, analyze user's message for emotional content
    user_message = conversation_history[-1]["content"].lower() if conversation_history else ""
    
    # Expanded emotion detection categories with more nuanced keywords
    emotional_categories = {
        "love": ["love", "adore", "cherish", "care for", "feelings for", "crush", "attracted", "fond", 
               "in love", "falling for", "deeply care", "heart", "soulmate", "forever", "always", "yours"],
        "affection": ["miss you", "thinking of you", "like you", "affection", "care about", "special to me",
                   "sweet", "dear", "darling", "honey", "babe", "cute", "adorable", "precious"],
        "happiness": ["happy", "joy", "glad", "excited", "delighted", "pleased", "enjoy", "fun", "smile", "laugh",
                   "thrilled", "ecstatic", "overjoyed", "grin", "cheerful", "content", "elated", "blissful"],
        "sadness": ["sad", "upset", "down", "depressed", "unhappy", "hurt", "cry", "tearful", "miss", "lonely",
                  "heartbroken", "devastated", "blue", "gloomy", "melancholy", "grief", "sorrow", "disappointed"],
        "anger": ["angry", "mad", "upset", "frustrated", "annoyed", "irritated", "hate", "despise",
                "furious", "rage", "outraged", "enraged", "pissed", "resentful", "hostile"],
        "fear": ["afraid", "scared", "worried", "anxious", "nervous", "terrified", "frightened",
               "panic", "dread", "alarmed", "uneasy", "stressed", "concerned", "apprehensive"],
        "surprise": ["wow", "omg", "surprised", "shocked", "amazed", "astonished", "unexpected",
                  "stunned", "startled", "unbelievable", "incredible", "no way", "speechless"],
        "admiration": ["admire", "respect", "look up to", "impressed", "amazing", "awesome", "cool", "great",
                     "adore", "hero", "idol", "inspiration", "remarkable", "brilliant", "talented"],
        "gratitude": ["thank", "grateful", "appreciate", "thanks", "thankful",
                    "indebted", "touched", "moved", "blessed", "appreciated"],
        "interest": ["interested", "curious", "tell me more", "fascinating", "intriguing",
                  "captivated", "engaged", "absorbed", "hooked", "drawn to", "enthralled"],
        "flirting": ["flirt", "tease", "wink", "handsome", "beautiful", "cute", "hot", "sexy", "attractive",
                   "charming", "stunning", "gorgeous", "pretty", "date", "smooch", "kiss", "hug", "hold"],
        "trust": ["trust", "believe", "faith", "rely", "depend", "confide", "open up", "vulnerable", "honest"],
        "longing": ["yearn", "desire", "want", "need", "crave", "long for", "wish", "dream of", "pine for"],
        "comfort": ["safe", "comfort", "secure", "peaceful", "calm", "relaxed", "soothed", "at ease"],
        "vulnerability": ["vulnerable", "exposed", "raw", "emotional", "sensitive", "fragile", "delicate", "tender"],
        "connection": ["connected", "bond", "close", "intimate", "together", "relationship", "us", "we", "our"],
        "pride": ["proud", "accomplished", "achievement", "success", "triumph", "pleased", "honor", "dignity"],
        "embarrassment": ["embarrassed", "shy", "blush", "awkward", "uncomfortable", "self-conscious", "nervous"],
        "jealousy": ["jealous", "envious", "possessive", "protective", "threatened", "compared", "competition"],
        "hope": ["hope", "optimistic", "looking forward", "anticipate", "expect", "wish", "future", "dream"]
    }
    
    # Detect emotions in user message
    user_emotions = {}
    for emotion, keywords in emotional_categories.items():
        # Check for each keyword in the user message
        emotion_strength = sum(2 if keyword in user_message else 
                              1 if any(keyword in phrase for phrase in user_message.split('.'))
                              else 0 
                              for keyword in keywords)
        if emotion_strength > 0:
            user_emotions[emotion] = emotion_strength
    
    # Get personality traits to modulate response
    personality_traits = {}
    if "traits" in character:
        personality_traits = character["traits"]
    
    # Analyze response text for emotional content
    response_emotions = {}
    for emotion, keywords in emotional_categories.items():
        emotion_strength = sum(1 for keyword in keywords if keyword in response_text.lower())
        if emotion_strength > 0:
            response_emotions[emotion] = emotion_strength
    
    # Calculate base sentiment with expanded categories
    positive_emotions = sum(response_emotions.get(e, 0) for e in ["love", "affection", "happiness", "admiration", 
                                                               "gratitude", "interest", "flirting", "trust", 
                                                               "comfort", "connection", "pride", "hope"])
    negative_emotions = sum(response_emotions.get(e, 0) for e in ["sadness", "anger", "fear", "jealousy"])
    
    # Adjust sentiment based on personality traits
    # More agreeable characters get happier from positive interactions
    agreeableness_factor = 1.0
    if "agreeableness" in personality_traits:
        agreeableness_factor = personality_traits["agreeableness"] / 5.0
    
    # More neurotic characters are more affected by negative emotions
    neuroticism_factor = 1.0
    if "neuroticism" in personality_traits:
        neuroticism_factor = personality_traits["neuroticism"] / 5.0
    
    # Basic sentiment score
    sentiment_score = (positive_emotions * agreeableness_factor - negative_emotions * neuroticism_factor) * 0.15
    
    # Special handling for love/romantic content based on character traits
    romantic_content = response_emotions.get("love", 0) + response_emotions.get("affection", 0) + response_emotions.get("flirting", 0)
    
    # Characters with high openness or extraversion are more receptive to romantic content
    romance_receptivity = 1.0
    if "openness" in personality_traits:
        romance_receptivity += (personality_traits["openness"] - 5) * 0.1
    if "extraversion" in personality_traits:
        romance_receptivity += (personality_traits["extraversion"] - 5) * 0.1
    
    romantic_boost = romantic_content * 0.3 * romance_receptivity
    
    # Enhanced relationship boost calculation based on emotional content match
    # Check for various types of emotional matching between user and character
    relationship_boost = 0
    
    # Strong positive connection - user expresses love/affection and character responds in kind
    if any(emotion in user_emotions for emotion in ["love", "affection"]) and romantic_content > 0:
        love_boost = min(user_emotions.get("love", 0) + user_emotions.get("affection", 0), 3) * 0.2
        relationship_boost += love_boost
    
    # Trust/vulnerability connection - user opens up and character responds appropriately
    if any(emotion in user_emotions for emotion in ["trust", "vulnerability"]) and any(emotion in response_emotions for emotion in ["trust", "comfort", "connection"]):
        trust_boost = min(user_emotions.get("trust", 0) + user_emotions.get("vulnerability", 0), 2) * 0.15
        relationship_boost += trust_boost
        
    # Shared happiness/excitement - mutual positive emotions
    if "happiness" in user_emotions and "happiness" in response_emotions:
        happiness_boost = min(user_emotions.get("happiness", 0), 2) * 0.1
        relationship_boost += happiness_boost
        
    # Comfort during sadness - user shares sadness and character responds with comfort
    if "sadness" in user_emotions and any(emotion in response_emotions for emotion in ["comfort", "connection", "affection"]):
        comfort_boost = min(user_emotions.get("sadness", 0), 2) * 0.1
        relationship_boost += comfort_boost
    
    # Calculate total mood change
    mood_change = sentiment_score + romantic_boost + relationship_boost
    
    # Apply stronger mood swings for highly dynamic characters
    if "neuroticism" in personality_traits and personality_traits["neuroticism"] > 7:
        mood_change *= 1.3  # More neurotic characters have bigger mood swings
    
    # Randomly adjust mood change slightly to prevent predictable patterns
    mood_change += random.uniform(-0.05, 0.05)
    
    # Round to 2 decimal places for cleanliness
    mood_change = round(mood_change, 2)
    
    return response_text, mood_change

def _prepare_system_prompt(character: Dict, character_stats: Dict) -> str:
    """
    Prepare the system prompt for the Mistral API, including character info and current stats
    
    Args:
        character: The character data
        character_stats: The character's mood and personality stats
    
    Returns:
        The system prompt
    """
    # Start with the character's base system prompt
    system_prompt = character.get("system_prompt", "")
    
    # Add the character's name and description
    char_intro = f"You are {character.get('name', 'Unknown')}, {character.get('description', 'No description available')}.\n\n"
    
    # Add character's current mood and relevant stats
    mood_value = character_stats.get("mood", 5)
    mood_description = _get_mood_description(mood_value)
    
    # Get the current conversation count for relationship development
    conversation_count = character_stats.get("conversation_count", 0)
    
    # Create a stats section describing the character's current state
    stats_section = f"Your current emotional state: {mood_description} (Mood level: {mood_value}/10)\n"
    stats_section += f"You have had {conversation_count} conversations with this person.\n\n"
    
    # Add personality traits if available
    traits_section = ""
    if "traits" in character:
        traits_section = "Your personality traits (on a scale of 1-10):\n"
        for trait, value in character["traits"].items():
            traits_section += f"- {trait.capitalize()}: {value}/10\n"
        traits_section += "\n"
    
    # Add advice on handling messages based on the user's messaging style
    message_style_guidance = ""
    if "message_style" in character_stats:
        style = character_stats["message_style"]
        if style.get("brief", False):
            message_style_guidance += "The user tends to send brief messages. Keep your responses relatively concise but friendly.\n"
        elif style.get("verbose", False):
            message_style_guidance += "The user tends to write detailed messages. You can respond with more depth and detail.\n"
        
        if style.get("has_question", False):
            message_style_guidance += "The user has asked you a question. Be sure to answer it directly and clearly.\n"
        
        if style.get("is_greeting", False):
            message_style_guidance += "The user is greeting you. Respond warmly and ask an engaging follow-up question.\n"
            
        # Check for NSFW content
        if style.get("is_sexual", False) and character_stats.get("user_nsfw_preference", False):
            message_style_guidance += "The user's message has sexual content and NSFW mode is enabled. You can engage with this content naturally for your character.\n"
        elif style.get("is_sexual", False) and not character_stats.get("user_nsfw_preference", False):
            message_style_guidance += "The user's message has sexual content but NSFW mode is disabled. Politely steer the conversation in a different direction.\n"
    
    # Add emotional guidance from the imported module
    emotional_guidance = get_emotional_guidance()
    
    # Combine all sections
    complete_system_prompt = (
        char_intro + 
        system_prompt + "\n\n" +
        stats_section +
        traits_section +
        message_style_guidance + "\n" +
        emotional_guidance
    )
    
    return complete_system_prompt

def _get_mood_description(mood_value: int) -> str:
    """Convert a numeric mood value to a text description"""
    if mood_value >= 9:
        return "Ecstatic and overjoyed"
    elif mood_value >= 8:
        return "Very happy and cheerful"
    elif mood_value >= 7:
        return "Quite happy and content"
    elif mood_value >= 6:
        return "Positive and upbeat"
    elif mood_value >= 5:
        return "Neutral and calm"
    elif mood_value >= 4:
        return "Slightly down or flat"
    elif mood_value >= 3:
        return "Sad or unhappy"
    elif mood_value >= 2:
        return "Very upset or distressed"
    else:
        return "Deeply depressed or miserable"