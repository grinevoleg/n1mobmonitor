import logging
import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from app.database import SessionLocal
from app.models import TelegramUser, UserNotificationSettings
from app.config import settings

logger = logging.getLogger(__name__)


class TelegramBotService:
    """Сервис Telegram бота для управления пользователями и уведомлениями"""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self._running = False
    
    def start(self, bot_token: str):
        """Запуск бота"""
        if not bot_token:
            logger.warning("Telegram bot token not provided, bot disabled")
            return
        
        if self._running:
            logger.warning("Bot already running")
            return
        
        # Создание приложения
        self.application = Application.builder().token(bot_token).build()
        
        # Регистрация обработчиков
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("notifications", self.cmd_notifications))
        
        # Admin команды
        self.application.add_handler(CommandHandler("users", self.cmd_users))
        self.application.add_handler(CommandHandler("approve", self.cmd_approve))
        self.application.add_handler(CommandHandler("reject", self.cmd_reject))
        self.application.add_handler(CommandHandler("setrole", self.cmd_setrole))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        
        # Обработчик текстовых сообщений (для кнопок меню)
        from telegram.ext import MessageHandler, filters
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_menu_buttons))
        
        # Обработчик callback query (для кнопок настроек)
        self.application.add_handler(CallbackQueryHandler(self.callback_users, pattern=r"^(approve|reject|role_admin|role_dev|role_mgr|user_info|users_refresh)_"))
        self.application.add_handler(CallbackQueryHandler(self.callback_settings, pattern="^toggle_"))
        
        # Запуск polling с созданием event loop
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self._running = True
        logger.info("Telegram bot starting polling...")
        
        try:
            loop.run_until_complete(self._run_polling())
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
        finally:
            self._running = False
    
    async def _run_polling(self):
        """Асинхронный запуск polling"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram bot started successfully")
        
        # Держим бота запущенным
        while self._running:
            await asyncio.sleep(1)
        
        # Остановка
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram bot stopped")
    
    def stop(self):
        """Остановка бота"""
        self._running = False
        logger.info("Telegram bot stopping...")
    
    def _get_db(self) -> Session:
        """Получение сессии БД"""
        return SessionLocal()
    
    def _get_or_create_user(self, telegram_id: str, username: str = None, full_name: str = None) -> TelegramUser:
        """Получение или создание пользователя"""
        db = self._get_db()
        try:
            user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            if not user:
                user = TelegramUser(
                    telegram_id=telegram_id,
                    username=username,
                    full_name=full_name,
                    status="pending",
                    role="manager"
                )
                db.add(user)
                db.commit()
                db.refresh(user)

                # Создание настроек уведомлений
                settings = UserNotificationSettings(telegram_id=user.id)
                db.add(settings)
                db.commit()
                
                logger.info(f"New user registered: {telegram_id} (@{username})")
            else:
                # Обновление информации
                if username and user.username != username:
                    user.username = username
                if full_name and user.full_name != full_name:
                    user.full_name = full_name
                user.updated_at = datetime.utcnow()
                db.commit()
            
            return db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
        finally:
            db.close()
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start - регистрация пользователя"""
        telegram_id = str(update.effective_user.id)
        username = update.effective_user.username
        full_name = update.effective_user.full_name

        user = self._get_or_create_user(telegram_id, username, full_name)

        # Создаём меню в зависимости от статуса
        if user.status == "approved":
            # Меню для авторизованных
            if user.role == "admin":
                keyboard = [["📊 Статус", "⚙️ Настройки"], ["👥 Пользователи", "📚 Справка"]]
            elif user.role == "developer":
                keyboard = [["📊 Статус", "⚙️ Настройки"], ["📚 Справка"]]
            else:  # manager
                keyboard = [["📊 Статус", "⚙️ Настройки"], ["📚 Справка"]]
            
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"✅ *Вы авторизованы!*\n\n"
                f"👤 *Роль:* {user.role}\n"
                f"🆔 *ID:* `{user.telegram_id}`\n\n"
                f"Выберите команду из меню или используйте /help",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        elif user.status == "rejected":
            await update.message.reply_text(
                f"❌ *Заявка отклонена*\n\n"
                f"Ваша заявка была отклонена администратором.\n"
                f"Обратитесь к администратору для уточнения деталей.",
                parse_mode='Markdown'
            )
        else:  # pending
            # Отправка уведомления админам
            await self._notify_admins(user, context)

            await update.message.reply_text(
                f"👋 *Здравствуйте, {full_name or 'пользователь'}!*\n\n"
                f"✅ Ваша заявка принята!\n\n"
                f"📋 *Что дальше:*\n"
                f"1️⃣ Ожидайте подтверждения от администратора\n"
                f"2️⃣ Обычно это занимает несколько минут\n"
                f"3️⃣ Вы получите уведомление когда заявку одобрят\n\n"
                f"🆔 *Ваш ID:* `{telegram_id}`\n"
                f"⏳ *Статус:* {user.status}",
                parse_mode='Markdown'
            )

    async def _notify_admins(self, user: TelegramUser, context: ContextTypes.DEFAULT_TYPE):
        """Уведомление админов о новой заявке"""
        db = self._get_db()
        try:
            admins = db.query(TelegramUser).filter(
                TelegramUser.role == "admin",
                TelegramUser.status == "approved"
            ).all()

            if not admins:
                logger.warning("Нет активных админов для уведомления")
                return

            message = (
                f"🔔 *Новая заявка!*\n\n"
                f"👤 *Пользователь:* {user.full_name or 'Не указано'}\n"
                f"📧 *Username:* @{user.username or 'Не указан'}\n"
                f"🆔 *ID:* `{user.telegram_id}`\n\n"
                f"⚡ *Быстрые действия:*\n"
                f"Используйте веб-интерфейс для управления:\n"
                f"http://localhost:8000/settings"
            )

            notified_count = 0
            for admin in admins:
                try:
                    await context.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    notified_count += 1
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin.telegram_id}: {e}")

            logger.info(f"Notified {notified_count}/{len(admins)} admins about new user")

        finally:
            db.close()
    
    async def handle_menu_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок меню"""
        text = update.message.text
        
        if text == "📊 Статус":
            await self.cmd_status(update, context)
        elif text == "⚙️ Настройки":
            await self.cmd_notifications(update, context)
        elif text == "📚 Справка":
            await self.cmd_help(update, context)
        elif text == "👥 Пользователи":
            await self.cmd_users(update, context)
    
    async def callback_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки настроек"""
        query = update.callback_query
        await query.answer()
        
        telegram_id = str(update.effective_user.id)
        data = query.data  # toggle_status_change, toggle_version_change, etc.
        
        db = self._get_db()
        try:
            user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            if not user or not user.notification_settings:
                await query.edit_message_text("❌ Ошибка: настройки не найдены")
                return
            
            settings = user.notification_settings
            
            # Переключение настройки
            if data == "toggle_status_change":
                settings.notify_status_change = not settings.notify_status_change
            elif data == "toggle_version_change":
                settings.notify_version_change = not settings.notify_version_change
            elif data == "toggle_error":
                settings.notify_error = not settings.notify_error
            elif data == "toggle_app_added":
                settings.notify_app_added = not settings.notify_app_added
            elif data == "toggle_unavailable":
                settings.notify_unavailable = not settings.notify_unavailable
            
            settings.updated_at = datetime.utcnow()
            db.commit()
            
            # Обновляем клавиатуру
            keyboard = [
                [InlineKeyboardButton(
                    "✅ Изменение статуса" if settings.notify_status_change else "❌ Изменение статуса",
                    callback_data="toggle_status_change"
                )],
                [InlineKeyboardButton(
                    "✅ Обновление версии" if settings.notify_version_change else "❌ Обновление версии",
                    callback_data="toggle_version_change"
                )],
                [InlineKeyboardButton(
                    "✅ Ошибки" if settings.notify_error else "❌ Ошибки",
                    callback_data="toggle_error"
                )],
                [InlineKeyboardButton(
                    "✅ Новые приложения" if settings.notify_app_added else "❌ Новые приложения",
                    callback_data="toggle_app_added"
                )],
                [InlineKeyboardButton(
                    "✅ Недоступно" if settings.notify_unavailable else "❌ Недоступно",
                    callback_data="toggle_unavailable"
                )],
            ]
            
            await query.edit_message_text(
                "⚙️ *Настройки уведомлений*\n\n"
                "Нажмите на кнопку чтобы переключить:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        finally:
            db.close()

    async def callback_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок управления пользователями"""
        query = update.callback_query
        await query.answer()
        
        telegram_id = str(update.effective_user.id)
        data = query.data
        
        logger.info(f"callback_users: {telegram_id} clicked {data}")
        
        # Кнопка обновления
        if data == "users_refresh":
            await query.delete_message()
            await self.cmd_users(update, context)
            return
        
        # Кнопка-разделитель
        if data == "separator":
            return
        
        db = self._get_db()
        try:
            admin = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            if not admin or admin.role != "admin" or admin.status != "approved":
                await query.answer("❌ Недостаточно прав", show_alert=True)
                return
            
            parts = data.split("_")
            action = parts[0]
            target_id = int(parts[-1])
            
            user = db.query(TelegramUser).filter(TelegramUser.id == target_id).first()
            if not user:
                await query.answer("❌ Пользователь не найден", show_alert=True)
                return
            
            if action == "approve":
                user.status = "approved"
                user.updated_at = datetime.utcnow()
                db.commit()
                
                # Уведомляем пользователя (без ожидания)
                try:
                    context.application.create_task(
                        context.bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"✅ *Ваша заявка одобрена!*\n\nРоль: *{user.role}*",
                            parse_mode='Markdown'
                        )
                    )
                except:
                    pass
                
                await query.answer(f"✅ {user.id} одобрен!")
                # Не вызываем cmd_users сразу - пользователь сам обновит
                
            elif action == "reject":
                user.status = "rejected"
                user.updated_at = datetime.utcnow()
                db.commit()
                
                try:
                    context.application.create_task(
                        context.bot.send_message(
                            chat_id=user.telegram_id,
                            text="❌ *Ваша заявка отклонена*",
                            parse_mode='Markdown'
                        )
                    )
                except:
                    pass
                
                await query.answer(f"❌ {user.id} отклонен!")
                
            elif action == "role":
                new_role = parts[1]
                role_map = {"admin": "admin", "dev": "developer", "mgr": "manager"}
                user.role = role_map.get(new_role, "manager")
                user.updated_at = datetime.utcnow()
                db.commit()
                
                role_name = {"admin": "👑 Admin", "dev": "💻 Developer", "mgr": "👤 Manager"}[new_role]
                
                # Уведомляем пользователя
                try:
                    context.application.create_task(
                        context.bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"🔔 *Ваша роль изменена!*\n\nНовая роль: *{user.role}*",
                            parse_mode='Markdown'
                        )
                    )
                except:
                    pass
                
                await query.answer(f"🔧 Роль: {role_name}!")
            
            elif action == "user_info":
                await query.answer(f"👤 {user.full_name or 'Без имени'}\n@{user.username or 'N/A'}\nРоль: {user.role}\nСтатус: {user.status}", show_alert=True)
            
        finally:
            db.close()
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status - проверка статуса"""
        telegram_id = str(update.effective_user.id)

        db = self._get_db()
        try:
            user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()

            if not user:
                await update.message.reply_text(
                    "❌ Вы не зарегистрированы.\n\nИспользуйте /start для регистрации."
                )
                return

            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(user.status, "❓")
            role_emoji = {"admin": "👑", "developer": "💻", "manager": "👤"}.get(user.role, "❓")

            await update.message.reply_text(
                f"*📊 Ваш статус:*\n\n"
                f"{status_emoji} *Статус:* {user.status}\n"
                f"{role_emoji} *Роль:* {user.role}\n"
                f"🆔 *ID:* `{user.telegram_id}`\n"
                f"📅 *Зарегистрирован:* {user.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Используйте /help для списка команд.",
                parse_mode='Markdown'
            )
        finally:
            db.close()

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help - справка"""
        telegram_id = str(update.effective_user.id)

        db = self._get_db()
        try:
            user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()

            if not user or user.status != "approved":
                await update.message.reply_text(
                    f"📚 *Справка*\n\n"
                    f"/start - Регистрация\n"
                    f"/status - Проверка статуса\n"
                    f"/help - Эта справка\n\n"
                    f"⏳ Ожидайте подтверждения администратора.",
                    parse_mode='Markdown'
                )
                return

            # Общие команды
            help_text = f"📚 *Справка*\n\n"
            help_text += f"*📋 Общие команды:*\n"
            help_text += f"/start - Регистрация\n"
            help_text += f"/status - Проверка статуса\n"
            help_text += f"/notifications - Настройка уведомлений\n"
            help_text += f"/help - Эта справка\n"

            # Команды для developer и admin
            if user.role in ["developer", "admin"]:
                help_text += f"\n*💻 Для разработчиков:*\n"
                help_text += f"/addapp <bundle_id|app_id> - Добавить приложение\n"
                help_text += f"/checkapp <app_id> - Проверить приложение\n"

            # Команды для admin
            if user.role == "admin":
                help_text += f"\n*👑 Для администраторов:*\n"
                help_text += f"/users - Список пользователей\n"
                help_text += f"/approve <id> - Одобрить\n"
                help_text += f"/reject <id> - Отклонить\n"
                help_text += f"/setrole <id> <role> - Сменить роль\n"
                help_text += f"/stats - Статистика\n"

            help_text += f"\n_Веб-интерфейс: http://localhost:8000_"

            await update.message.reply_text(help_text)
        finally:
            db.close()
    
    async def cmd_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /notifications - настройка уведомлений"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not user or user.status != "approved":
                await update.message.reply_text("Сначала дождитесь подтверждения.")
                return
            
            settings = user.notification_settings
            
            keyboard = [
                [InlineKeyboardButton(
                    "✅ Изменение статуса" if settings.notify_status_change else "❌ Изменение статуса",
                    callback_data="toggle_status_change"
                )],
                [InlineKeyboardButton(
                    "✅ Обновление версии" if settings.notify_version_change else "❌ Обновление версии",
                    callback_data="toggle_version_change"
                )],
                [InlineKeyboardButton(
                    "✅ Ошибки" if settings.notify_error else "❌ Ошибки",
                    callback_data="toggle_error"
                )],
                [InlineKeyboardButton(
                    "✅ Новые приложения" if settings.notify_app_added else "❌ Новые приложения",
                    callback_data="toggle_app_added"
                )],
                [InlineKeyboardButton(
                    "✅ Недоступно" if settings.notify_unavailable else "❌ Недоступно",
                    callback_data="toggle_unavailable"
                )],
            ]
            
            await update.message.reply_text(
                "⚙️ *Настройки уведомлений*\n\n"
                "Нажмите на кнопку чтобы переключить:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        finally:
            db.close()
    
    async def cmd_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /users - управление пользователями (admin)"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            admin = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not admin or admin.role != "admin" or admin.status != "approved":
                await update.message.reply_text("❌ Недостаточно прав\n\nТолько администраторы могут управлять пользователями.", parse_mode='Markdown')
                return
            
            users = db.query(TelegramUser).order_by(TelegramUser.created_at.desc()).limit(10).all()
            
            if not users:
                await update.message.reply_text("👥 Нет пользователей")
                return
            
            # Главное меню управления
            keyboard = []
            
            for u in users:
                status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(u.status, "❓")
                role_emoji = {"admin": "👑", "developer": "💻", "manager": "👤"}.get(u.role, "❓")
                
                user_name = f"@{u.username}" if u.username else (u.full_name or f"ID:{u.id}")
                
                # Кнопка с информацией о пользователе
                if u.status == "pending":
                    # Для новых - одобрить/отклонить
                    keyboard.append([
                        InlineKeyboardButton(f"{status_emoji} {user_name}", callback_data=f"user_info_{u.id}")
                    ])
                    keyboard.append([
                        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{u.id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{u.id}")
                    ])
                else:
                    # Для активных - смена роли
                    keyboard.append([
                        InlineKeyboardButton(f"{status_emoji}{role_emoji} {user_name}", callback_data=f"user_info_{u.id}")
                    ])
                    keyboard.append([
                        InlineKeyboardButton("👑 Admin", callback_data=f"role_admin_{u.id}"),
                        InlineKeyboardButton("💻 Dev", callback_data=f"role_dev_{u.id}"),
                        InlineKeyboardButton("👤 Mgr", callback_data=f"role_mgr_{u.id}")
                    ])
                keyboard.append([InlineKeyboardButton("─────────────", callback_data="separator")])
            
            keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="users_refresh")])
            
            await update.message.reply_text(
                "👥 *Управление пользователями*\n\n"
                "Нажмите на кнопку чтобы изменить роль или статус:\n"
                "👑 - Admin | 💻 - Developer | 👤 - Manager\n"
                "✅ - Одобрить | ❌ - Отклонить",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        finally:
            db.close()
    
    async def cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /approve - одобрить пользователя (admin)"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            admin = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not admin or admin.role != "admin" or admin.status != "approved":
                await update.message.reply_text("❌ Недостаточно прав")
                return
            
            if not context.args or not context.args[0].isdigit():
                await update.message.reply_text("Используйте: /approve <user_id>")
                return
            
            user_id = int(context.args[0])
            user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
            
            if not user:
                await update.message.reply_text("❌ Пользователь не найден")
                return
            
            user.status = "approved"
            user.approved_by = admin.id
            user.updated_at = datetime.utcnow()
            db.commit()
            
            # Уведомление пользователя
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"✅ *Заявка одобрена!*\n\nРоль: *{user.role}*\n\nИспользуйте /help для списка команд.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")
            
            await update.message.reply_text(f"✅ Пользователь @{user.username or user.id} одобрен!")
        finally:
            db.close()
    
    async def cmd_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /reject - отклонить пользователя (admin)"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            admin = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not admin or admin.role != "admin" or admin.status != "approved":
                await update.message.reply_text("❌ Недостаточно прав")
                return
            
            if not context.args or not context.args[0].isdigit():
                await update.message.reply_text("Используйте: /reject <user_id>")
                return
            
            user_id = int(context.args[0])
            user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
            
            if not user:
                await update.message.reply_text("❌ Пользователь не найден")
                return
            
            user.status = "rejected"
            user.updated_at = datetime.utcnow()
            db.commit()
            
            # Уведомление пользователя
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text="❌ *Заявка отклонена*\n\nОбратитесь к администратору.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")
            
            await update.message.reply_text(f"❌ Пользователь @{user.username or user.id} отклонен!")
        finally:
            db.close()
    
    async def cmd_setrole(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /setrole - сменить роль (admin)"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            admin = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not admin or admin.role != "admin" or admin.status != "approved":
                await update.message.reply_text("❌ Недостаточно прав")
                return
            
            if len(context.args) < 2:
                await update.message.reply_text("Используйте: /setrole <user_id> <role>")
                return
            
            user_id = int(context.args[0])
            role_name = context.args[1].lower()
            
            if role_name not in ["admin", "developer", "manager"]:
                await update.message.reply_text("Роль должна быть: admin, developer, или manager")
                return
            
            user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
            
            if not user:
                await update.message.reply_text("❌ Пользователь не найден")
                return
            
            user.role = role_name
            user.updated_at = datetime.utcnow()
            db.commit()
            
            await update.message.reply_text(f"✅ Роль пользователя @{user.username or user.id} изменена на {role_name}")
        finally:
            db.close()
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - статистика (admin)"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            admin = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not admin or admin.role != "admin" or admin.status != "approved":
                await update.message.reply_text("❌ Недостаточно прав")
                return
            
            total = db.query(TelegramUser).count()
            pending = db.query(TelegramUser).filter(TelegramUser.status == "pending").count()
            approved = db.query(TelegramUser).filter(TelegramUser.status == "approved").count()
            rejected = db.query(TelegramUser).filter(TelegramUser.status == "rejected").count()
            
            admins = db.query(TelegramUser).filter(TelegramUser.role == "admin").count()
            developers = db.query(TelegramUser).filter(TelegramUser.role == "developer").count()
            managers = db.query(TelegramUser).filter(TelegramUser.role == "manager").count()
            
            await update.message.reply_text(
                f"📊 *Статистика*\n\n"
                f"*Всего:* {total}\n"
                f"*По статусу:*\n"
                f"  ⏳ Ожидают: {pending}\n"
                f"  ✅ Одобрено: {approved}\n"
                f"  ❌ Отклонено: {rejected}\n\n"
                f"*По ролям:*\n"
                f"  👑 Admin: {admins}\n"
                f"  💻 Developer: {developers}\n"
                f"  👤 Manager: {managers}",
                parse_mode='Markdown'
            )
        finally:
            db.close()


# Singleton экземпляр
telegram_bot_service = TelegramBotService()
