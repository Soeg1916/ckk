import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from character_manager import CharacterManager

logger = logging.getLogger(__name__)

# Admin User ID - this should be the Telegram ID of the admin user
ADMIN_USER_ID = 1159603709

async def admin_delete_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to delete any character (admin only)"""
    user_id = update.effective_user.id
    
    # Check if the user is an admin
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    # Check if a character ID was provided
    if not context.args:
        # No character ID provided, ask the admin to choose from a list
        character_manager = CharacterManager()
        all_characters = character_manager.get_all_characters()
        
        # Create inline keyboard for character selection
        keyboard = []
        
        # Add preset characters header
        keyboard.append([InlineKeyboardButton("--- Preset Characters ---", callback_data="admin_header")])
        
        # Add preset character buttons
        preset_buttons = []
        for char_id, char in all_characters.items():
            if not char_id.startswith("custom_"):
                button_text = f"{char['name']} {'🔞' if char.get('nsfw', False) else ''}"
                preset_buttons.append(
                    InlineKeyboardButton(button_text, callback_data=f"admin_delete:{char_id}")
                )
        
        # Arrange preset character buttons in rows of 2
        for i in range(0, len(preset_buttons), 2):
            row = preset_buttons[i:i+2]  # Take 2 buttons at a time
            keyboard.append(row)
        
        # Add custom characters header
        keyboard.append([InlineKeyboardButton("--- Custom Characters ---", callback_data="custom_header")])
        
        # Add custom character buttons
        custom_buttons = []
        for char_id, char in all_characters.items():
            if char_id.startswith("custom_"):
                button_text = f"{char['name']} {'🔞' if char.get('nsfw', False) else ''}"
                custom_buttons.append(
                    InlineKeyboardButton(button_text, callback_data=f"admin_delete:{char_id}")
                )
        
        # Arrange custom character buttons in rows of 2
        for i in range(0, len(custom_buttons), 2):
            row = custom_buttons[i:i+2]  # Take 2 buttons at a time
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👮‍♂️ *Admin Mode: Delete Character* 👮‍♂️\n\n"
            "Select a character to delete:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        # Character ID provided, delete it directly
        character_id = context.args[0]
        character_manager = CharacterManager()
        character = character_manager.get_character(character_id)
        
        if not character:
            await update.message.reply_text(f"⚠️ Character with ID '{character_id}' not found.")
            return
        
        # Confirm deletion
        keyboard = [
            [InlineKeyboardButton("✅ Yes, delete this character", callback_data=f"confirm_admin_delete:{character_id}")],
            [InlineKeyboardButton("❌ No, keep this character", callback_data="cancel_admin_delete")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Are you sure you want to delete the character '{character['name']}'?\n\n"
            "This action cannot be undone.",
            reply_markup=reply_markup
        )

async def admin_create_character_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the admin character creation process (admin only)"""
    user_id = update.effective_user.id
    
    # Check if the user is an admin
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    await update.message.reply_text(
        "👮‍♂️ *Admin Mode: Create Character* 👮‍♂️\n\n"
        "Let's create a new character! 🎭\n\n"
        "First, what's the name of the character?\n"
        "Send me the name or use /cancel to stop the creation process.",
        parse_mode="Markdown"
    )
    
    # Initialize character creation state
    context.user_data["admin_character_creation"] = {"step": "name"}
    
    return 1  # Move to next step

async def admin_process_character_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process admin character creation steps"""
    user_id = update.effective_user.id
    
    # Check if the user is an admin
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    # Get the current creation state
    creation_data = context.user_data.get("admin_character_creation", {})
    current_step = creation_data.get("step", "name")
    
    if current_step == "name":
        # Save the character name
        name = update.message.text.strip()
        
        if len(name) > 30:
            await update.message.reply_text("⚠️ Character name is too long. Please keep it under 30 characters.")
            return 1  # Stay on this step
        
        creation_data["name"] = name
        creation_data["step"] = "description"
        
        await update.message.reply_text(
            f"Great! The character will be named '{name}'.\n\n"
            "Now, write a detailed description for this character. This should include their background, "
            "personality, and any other important details.\n\n"
            "Send me the description or use /cancel to stop the creation process."
        )
        
        return 2  # Move to description step
    
    elif current_step == "description":
        # Save the character description
        description = update.message.text.strip()
        
        if len(description) < 10:
            await update.message.reply_text("⚠️ Description is too short. Please provide more details.")
            return 2  # Stay on this step
        
        creation_data["description"] = description
        creation_data["step"] = "traits"
        
        await update.message.reply_text(
            "Perfect! Now let's set the personality traits for this character.\n\n"
            "Please provide values for the following traits on a scale of 1-10, "
            "separated by commas in this order:\n\n"
            "friendliness, humor, intelligence, empathy, energy\n\n"
            "For example: 7, 5, 9, 6, 8\n\n"
            "Send me the values or use /cancel to stop the creation process."
        )
        
        return 3  # Move to traits step
    
    elif current_step == "traits":
        # Parse trait values
        try:
            trait_values = [int(value.strip()) for value in update.message.text.split(",")]
            if len(trait_values) != 5:
                await update.message.reply_text("⚠️ Please provide exactly 5 trait values.")
                return 3  # Stay on this step
            
            for value in trait_values:
                if value < 1 or value > 10:
                    await update.message.reply_text("⚠️ All trait values must be between 1 and 10.")
                    return 3  # Stay on this step
            
            # Save trait values
            creation_data["traits"] = {
                "friendliness": trait_values[0],
                "humor": trait_values[1],
                "intelligence": trait_values[2],
                "empathy": trait_values[3],
                "energy": trait_values[4]
            }
            creation_data["step"] = "system_prompt"
            
            await update.message.reply_text(
                "Excellent! Now let's set the system prompt for this character.\n\n"
                "The system prompt is the instruction given to the AI to help it "
                "assume the character's persona. Be detailed and specific about how "
                "the character should behave, speak, and interact.\n\n"
                "Send me the system prompt or use /cancel to stop the creation process."
            )
            
            return 4  # Move to system prompt step
        
        except ValueError:
            await update.message.reply_text("⚠️ Invalid input. Please provide numbers between 1-10 separated by commas.")
            return 3  # Stay on this step
    
    elif current_step == "system_prompt":
        # Save the system prompt
        system_prompt = update.message.text.strip()
        
        if len(system_prompt) < 20:
            await update.message.reply_text("⚠️ System prompt is too short. Please provide more detailed instructions.")
            return 4  # Stay on this step
        
        creation_data["system_prompt"] = system_prompt
        creation_data["step"] = "nsfw"
        
        # Ask about NSFW status
        keyboard = [
            [InlineKeyboardButton("Yes - Enable NSFW", callback_data="admin_nsfw:yes")],
            [InlineKeyboardButton("No - Keep SFW", callback_data="admin_nsfw:no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Almost done! Should this character have NSFW mode enabled?\n\n"
            "NSFW mode allows the character to engage with mature/adult content.",
            reply_markup=reply_markup
        )
        
        return 5  # Move to NSFW step (final step)
    
    return 0  # End conversation by default

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Check if the user is an admin
    if user_id != ADMIN_USER_ID:
        await query.message.reply_text("⚠️ These actions are only available to administrators.")
        return
    
    if query.data.startswith("admin_delete:"):
        character_id = query.data.split(":")[1]
        character_manager = CharacterManager()
        character = character_manager.get_character(character_id)
        
        if not character:
            await query.edit_message_text(f"⚠️ Character with ID '{character_id}' not found.")
            return
        
        # Ask for confirmation before deleting
        keyboard = [
            [InlineKeyboardButton("✅ Yes, delete this character", callback_data=f"confirm_admin_delete:{character_id}")],
            [InlineKeyboardButton("❌ No, keep this character", callback_data="cancel_admin_delete")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Are you sure you want to delete the character '{character['name']}'?\n\n"
            "This action cannot be undone.",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("confirm_admin_delete:"):
        character_id = query.data.split(":")[1]
        character_manager = CharacterManager()
        character = character_manager.get_character(character_id)
        
        if not character:
            await query.edit_message_text(f"⚠️ Character with ID '{character_id}' not found.")
            return
        
        character_name = character["name"]
        
        # Delete the character using admin_delete_character
        success = character_manager.admin_delete_character(user_id, character_id)
        
        if success:
            await query.edit_message_text(
                f"✅ Successfully deleted the character '{character_name}'."
            )
        else:
            await query.edit_message_text(
                f"❌ Failed to delete the character '{character_name}'."
            )
    
    elif query.data == "cancel_admin_delete":
        await query.edit_message_text("Deletion cancelled. The character has been preserved.")
    
    elif query.data.startswith("admin_nsfw:"):
        choice = query.data.split(":")[1]
        creation_data = context.user_data.get("admin_character_creation", {})
        
        # Set NSFW status - default to False unless explicitly set to "yes"
        creation_data["nsfw"] = (choice == "yes")
        # Double check to make sure nsfw is False by default
        if "nsfw" not in creation_data:
            creation_data["nsfw"] = False
        
        # Create the character
        character_manager = CharacterManager()
        character_id = character_manager.admin_create_character(
            admin_id=user_id,
            name=creation_data["name"],
            description=creation_data["description"],
            traits=creation_data["traits"],
            system_prompt=creation_data["system_prompt"],
            nsfw=creation_data["nsfw"]
        )
        
        # Get the full character data
        character = character_manager.get_character(character_id)
        
        if character:
            await query.edit_message_text(
                f"✅ Character '{character['name']}' has been created successfully!\n\n"
                f"Character ID: {character_id}\n"
                f"NSFW mode: {'Enabled' if creation_data['nsfw'] else 'Disabled'}\n\n"
                "This character is now available to all users."
            )
        else:
            await query.edit_message_text(
                "❌ Failed to create the character. Please try again."
            )
        
        # Clear the creation data
        if "admin_character_creation" in context.user_data:
            del context.user_data["admin_character_creation"]

async def admin_list_all_characters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all characters in the system (admin only)"""
    user_id = update.effective_user.id
    
    # Check if the user is an admin
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    try:
        character_manager = CharacterManager()
        all_characters = character_manager.get_all_characters()
        
        # Send a simple header first
        header = (
            "👮‍♂️ ADMIN MODE: CHARACTER DATABASE 👮‍♂️\n\n"
            f"Total Characters: {len(all_characters)}\n"
        )
        await update.message.reply_text(header)
        
        # Create separate messages for preset and custom characters
        preset_chars = []
        custom_chars = []
        
        # Process all characters
        for char_id, char in all_characters.items():
            if not char_id.startswith("custom_"):
                # It's a preset character
                preset_chars.append(f"{char_id} - {char['name']}")
            else:
                # It's a custom character
                status = ""
                if char.get("is_public", False):
                    status = " [PUBLIC]"
                if char.get("pending_approval", False):
                    status = " [PENDING]"
                creator = char.get("creator_id", "unknown")
                custom_chars.append(f"{char_id} - {char['name']}{status} (Creator: {creator})")
        
        # Send preset characters list
        if preset_chars:
            preset_msg = "PRESET CHARACTERS:\n" + "\n".join(preset_chars)
            await update.message.reply_text(preset_msg)
        
        # Send custom characters list
        if custom_chars:
            custom_msg = "CUSTOM CHARACTERS:\n" + "\n".join(custom_chars)
            await update.message.reply_text(custom_msg)
        
        # Send commands as a separate message
        commands = (
            "AVAILABLE COMMANDS:\n"
            "/admin_delete - Delete any character\n"
            "/admin_create - Create a new character\n"
            "/admin_list - Show all characters\n"
            "/pending - List characters pending approval\n"
            "/approve - Approve a character\n"
            "/reject - Reject a character"
        )
        await update.message.reply_text(commands)
        
    except Exception as e:
        # Simple error handling
        logger.error(f"Error listing characters: {e}")
        await update.message.reply_text(f"Error listing characters. Please try again later.")