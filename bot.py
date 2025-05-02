import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

from character_manager import CharacterManager
from conversation_handler import handle_message
from utils import (
    handle_error, list_characters, show_current_character, 
    reset_conversation, show_character_stats, create_character_start,
    process_character_creation, delete_character, cancel_creation,
    toggle_nsfw, SELECTING_NAME, ENTERING_DESCRIPTION, SELECTING_TRAITS
)
from character_sharing import (
    request_share_character, admin_list_pending_characters,
    admin_approve_character, admin_reject_character, list_public_characters
)
from admin_commands import (
    admin_delete_character, admin_create_character_start,
    admin_process_character_creation, handle_admin_callback,
    admin_list_all_characters, ADMIN_USER_ID
)

logger = logging.getLogger(__name__)

async def post_init(application: Application) -> None:
    """Callback that's called after the application is initialized but before the bot is running."""
    try:
        # Get the bot info and save the username to environment
        bot_info = await application.bot.get_me()
        if bot_info and bot_info.username:
            import os
            os.environ["BOT_USERNAME"] = bot_info.username
            logging.info(f"Bot username saved to environment: {bot_info.username}")
    except Exception as e:
        logging.error(f"Error in post_init callback: {e}")

def setup_bot(token: str) -> Application:
    """Set up the Telegram bot with all handlers"""
    # Initialize the character manager
    character_manager = CharacterManager()
    
    # Create the Application instance with post-init callback
    application = Application.builder().token(token).post_init(post_init).build()
    
    # Add conversation handler for character creation
    creation_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create_character_start)],
        states={
            SELECTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_character_creation)],
            ENTERING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_character_creation)],
            SELECTING_TRAITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_character_creation)],
        },
        fallbacks=[CommandHandler("cancel", cancel_creation)],
        # Remove per_message=True since we're not using CallbackQueryHandler
    )
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("characters", list_characters))
    application.add_handler(CommandHandler("character", show_current_character))
    application.add_handler(CommandHandler("reset", reset_conversation))
    application.add_handler(CommandHandler("stats", show_character_stats))
    application.add_handler(CommandHandler("delete", delete_character))
    application.add_handler(CommandHandler("nsfw", toggle_nsfw))
    
    # Add character sharing commands
    application.add_handler(CommandHandler("share", request_share_character))
    application.add_handler(CommandHandler("public", list_public_characters))
    application.add_handler(CommandHandler("pending", admin_list_pending_characters))
    application.add_handler(CommandHandler("approve", admin_approve_character))
    application.add_handler(CommandHandler("reject", admin_reject_character))
    
    # Add admin commands
    application.add_handler(CommandHandler("admin_delete", admin_delete_character))
    application.add_handler(CommandHandler("admin_create", admin_create_character_start))
    application.add_handler(CommandHandler("admin_list", admin_list_all_characters))
    
    # Add admin character creation conversation handler
    admin_creation_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin_create", admin_create_character_start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_process_character_creation)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_process_character_creation)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_process_character_creation)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_process_character_creation)],
            # Move the CallbackQueryHandler outside the ConversationHandler since we're mixing handler types
            # 5: [CallbackQueryHandler(handle_admin_callback, pattern=r"^admin_nsfw:")],
            5: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_process_character_creation)],
        },
        fallbacks=[CommandHandler("cancel", cancel_creation)]
    )
    
    # Add conversation handler for character creation
    application.add_handler(creation_conv_handler)
    application.add_handler(admin_creation_conv_handler)
    
    # Register callback query handlers for inline buttons
    # Add admin callback handler for admin-specific actions
    application.add_handler(CallbackQueryHandler(handle_admin_callback, pattern=r"^(admin_|confirm_admin_)"
    ))
    # Add regular callback handler for all other actions
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Register message handler for general messages in private chats
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
        handle_message
    ))
    
    # Register message handler for group chats - handle only when the bot is mentioned (@botname) or 
    # when the message is a reply to the bot's message
    application.add_handler(MessageHandler(
        (filters.TEXT & ~filters.COMMAND & 
        (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) &
        (filters.REPLY | filters.Entity("mention"))),
        handle_message
    ))
    
    # Register error handler
    application.add_error_handler(handle_error)
    
    return application

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when the command /start is issued."""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("Choose a Character", callback_data="show_characters")],
        [InlineKeyboardButton("Create Custom Character", callback_data="create_character")],
        [InlineKeyboardButton("Public Characters", callback_data="public_characters")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Hello {user.first_name}! I'm a character-based chat bot powered by Mistral AI.\n\n"
        "I can take on the personality of various fictional characters and chat with you as them!\n\n"
        "Use /help to see all available commands, or tap a button below to get started:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message when the command /help is issued."""
    # Create a simple plain text help message - no markdown formatting
    help_text = (
        "🤖 Character Chat Bot Help 🤖\n\n"
        "Available Commands:\n"
        "/characters - List all available characters\n"
        "/character - Show your current character\n"
        "/create - Create a custom character\n"
        "/delete - Delete a custom character\n"
        "/reset - Reset conversation with current character\n"
        "/stats - Show character's mood and personality stats\n"
        "/nsfw - Toggle NSFW mode for current character\n"
        "/share - Request to share your custom character with the community\n"
        "/public - Browse community-shared characters\n"
        "/help - Show this help message\n\n"
        
        "How to use:\n"
        "1. Select a character using /characters\n"
        "2. Start chatting with them!\n"
        "3. The character will respond based on their personality.\n"
        "4. Their mood might change based on your conversation.\n\n"
        
        "Group Chat Support:\n"
        "In group chats, interact with the bot by:\n"
        "- Mentioning the bot using @botname\n"
        "- Replying directly to the bot's messages\n\n"
        
        "Custom Characters:\n"
        "Create your own characters with /create\n"
        "You can set their name, background, and personality traits.\n"
        "Share your creations with the community using /share\n\n"
        
        "NSFW Mode:\n"
        "Use /nsfw to toggle NSFW mode for your current character.\n"
        "NSFW mode allows more mature and adult-themed conversations."
    )
    
    # Add admin-specific commands if user is an admin
    user_id = update.effective_user.id
    if user_id == ADMIN_USER_ID:
        admin_text = (
            "\n\nAdmin Commands:\n"
            "/admin_list - List all characters in the database\n"
            "/admin_delete - Delete any character\n" 
            "/admin_create - Create new admin character\n"
            "/pending - List all characters pending approval\n"
            "/approve <characterid> - Approve a character for public sharing\n"
            "/reject <characterid> - Reject a character for public sharing"
        )
        help_text += admin_text
    
    keyboard = [
        [InlineKeyboardButton("Choose a Character", callback_data="show_characters")],
        [InlineKeyboardButton("Create Custom Character", callback_data="create_character")],
        [InlineKeyboardButton("Public Characters", callback_data="public_characters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the combined help message with buttons - without any parsing mode
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callback queries"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "public_characters":
        # Show public characters
        await list_public_characters(update, context)
        return
        
    elif query.data == "show_characters":
        # Create a new message instead of trying to update
        character_manager = CharacterManager()
        
        # Get all characters
        all_characters = character_manager.get_all_characters()
        
        # Get the user's custom characters
        user_id = update.effective_user.id
        user_custom_characters = character_manager.get_user_characters(user_id)
        
        # Create inline keyboard for character selection
        keyboard = []
        
        # Add preset characters header
        keyboard.append([InlineKeyboardButton("--- Preset Characters ---", callback_data="preset_header")])
        
        # Collect preset character buttons
        preset_buttons = []
        for char_id, char in all_characters.items():
            if not char_id.startswith("custom_"):
                nsfw_mode = char.get("nsfw", False)
                button_text = f"{char['name']} {'🔞' if nsfw_mode else ''}"
                preset_buttons.append(
                    InlineKeyboardButton(button_text, callback_data=f"select_character:{char_id}")
                )
        
        # Arrange preset character buttons in rows of 2
        for i in range(0, len(preset_buttons), 2):
            row = preset_buttons[i:i+2]  # Take 2 buttons at a time
            keyboard.append(row)
        
        # Add custom characters
        if user_custom_characters:
            keyboard.append([InlineKeyboardButton("--- Your Custom Characters ---", callback_data="custom_header")])
            
            # Collect custom character buttons
            custom_buttons = []
            for char_id in user_custom_characters:
                if char_id in all_characters:
                    nsfw_mode = all_characters[char_id].get("nsfw", False)
                    button_text = f"{all_characters[char_id]['name']} {'🔞' if nsfw_mode else ''}"
                    custom_buttons.append(
                        InlineKeyboardButton(button_text, callback_data=f"select_character:{char_id}")
                    )
            
            # Arrange custom character buttons in rows of 3
            for i in range(0, len(custom_buttons), 3):
                row = custom_buttons[i:i+3]  # Take 3 buttons at a time
                keyboard.append(row)
        
        # Add button to create a new character
        keyboard.append([InlineKeyboardButton("Create New Character", callback_data="create_character")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Choose a character to chat with:",
            reply_markup=reply_markup
        )
    elif query.data == "create_character":
        # Send a new message to start character creation
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Let's create a custom character! 🎭\n\n"
            "First, what's the name of your character?\n"
            "Send me the name or use /cancel to stop the creation process."
        )
        
        # Initialize character creation state
        context.user_data["character_creation"] = {"step": "name"}
        
        # Set conversation state
        context.user_data["state"] = SELECTING_NAME
    elif query.data == "help":
        # Call the help command directly to avoid duplication
        await help_command(update, context)
    elif query.data.startswith("select_character:"):
        character_id = query.data.split(":")[1]
        # Set the selected character for the user
        if not context.user_data.get("selected_character"):
            context.user_data["selected_character"] = {}
        context.user_data["selected_character"] = character_id
        
        # Get character details from character manager
        character_manager = CharacterManager()
        character = character_manager.get_character(character_id)
        
        # Handle case where character might not exist
        if not character:
            await query.edit_message_text(
                f"Sorry, I couldn't find character with ID: {character_id}.\n\n"
                f"Please try selecting a different character."
            )
            return
            
        character_manager.set_user_selected_character(update.effective_user.id, character_id)
        
        # Show NSFW status - safe access with get() to avoid issues
        nsfw_mode = character.get("nsfw", False)
        name = character.get("name", "Unknown Character")
        description = character.get("description", "No description available")
        
        nsfw_text = "Enabled (character will engage with ANY adult content)" if nsfw_mode else "Disabled (use /nsfw to enable)"
        
        await query.edit_message_text(
            f"You are now chatting with *{name}*!\n\n"
            f"{description}\n\n"
            f"NSFW mode: {nsfw_text}\n\n"
            "Start chatting now! Character will match your message length and energy level.",
            parse_mode="Markdown"
        )
    elif query.data.startswith("delete_character:"):
        character_id = query.data.split(":")[1]
        character_manager = CharacterManager()
        
        # Get the character name for confirmation
        all_characters = character_manager.get_all_characters()
        character_name = all_characters.get(character_id, {}).get("name", "Unknown Character")
        
        # Ask for confirmation before deleting
        keyboard = [
            [InlineKeyboardButton("✅ Yes, delete this character", callback_data=f"confirm_delete:{character_id}")],
            [InlineKeyboardButton("❌ No, keep this character", callback_data="cancel_delete")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Are you sure you want to delete the character '{character_name}'?\n\n"
            "This action cannot be undone.",
            reply_markup=reply_markup
        )
    elif query.data.startswith("confirm_delete:"):
        character_id = query.data.split(":")[1]
        character_manager = CharacterManager()
        
        # Get the character name for confirmation
        all_characters = character_manager.get_all_characters()
        character_name = all_characters.get(character_id, {}).get("name", "Unknown Character")
        
        # Delete the character
        success = character_manager.delete_custom_character(update.effective_user.id, character_id)
        
        if success:
            await query.edit_message_text(
                f"✅ Successfully deleted the character '{character_name}'."
            )
        else:
            await query.edit_message_text(
                f"❌ Failed to delete '{character_name}'. You can only delete your own custom characters."
            )
    elif query.data == "cancel_delete":
        await query.edit_message_text(
            "Character deletion cancelled."
        )
    elif query.data == "public_characters":
        # Show public characters
        character_manager = CharacterManager()
        public_characters = character_manager.get_public_characters()
        
        if not public_characters:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="There are no public custom characters available yet. Be the first to share one with /share!"
            )
            return
        
        # Create the message text
        message_text = "🌍 *Community Shared Characters* 🌍\n\n"
        
        # Create inline keyboard for character selection
        keyboard = []
        
        for char_id, char in public_characters.items():
            nsfw_mode = char.get("nsfw", False)
            button_text = f"{char['name']} {'🔞' if nsfw_mode else ''}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_character:{char_id}")])
            
            # Add details to message text
            message_text += f"*{char['name']}*"
            message_text += f" 🔞" if nsfw_mode else ""
            message_text += f"\n{char['description'][:100]}...\n\n"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
