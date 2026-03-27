import logging
import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from app.database import SessionLocal
from app.models import TelegramUser, UserNotificationSettings, UserRole, UserStatus
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
                    status=UserStatus.pending,
                    role=UserRole.manager
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
            
            return user
        finally:
            db.close()
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start - регистрация пользователя"""
        telegram_id = str(update.effective_user.id)
        username = update.effective_user.username
        full_name = update.effective_user.full_name
        
        user = self._get_or_create_user(telegram_id, username, full_name)
        
        if user.status == UserStatus.approved:
            await update.message.reply_text(
                f"✅ Вы уже авторизованы!\n\n"
                f"Роль: *{user.role.value}*\n"
                f"ID: `{user.telegram_id}`\n\n"
                f"Используйте /help для списка команд.",
                parse_mode='Markdown'
            )
        elif user.status == UserStatus.rejected:
            await update.message.reply_text(
                "❌ Ваша заявка была отклонена.\n"
                "Обратитесь к администратору."
            )
        else:
            # Отправка уведомления админам
            await self._notify_admins(user, update)
            
            await update.message.reply_text(
                f"👋 Здравствуйте, {user.full_name or 'пользователь'}!\n\n"
                f"Ваша заявка на регистрацию отправлена.\n"
                f"Ожидайте подтверждения от администратора.\n\n"
                f"Ваш ID: `{user.telegram_id}`\n"
                f"Статус: ⏳ {user.status.value}",
                parse_mode='Markdown'
            )
    
    async def _notify_admins(self, user: TelegramUser, update: Update):
        """Уведомление админов о новой заявке"""
        db = self._get_db()
        try:
            admins = db.query(TelegramUser).filter(
                TelegramUser.role == UserRole.admin,
                TelegramUser.status == UserStatus.approved
            ).all()
            
            message = (
                f"🔔 *Новая заявка!*\n\n"
                f"Пользователь: {user.full_name or 'Не указано'}\n"
                f"Username: @{user.username or 'Не указан'}\n"
                f"ID: `{user.telegram_id}`\n\n"
                f"Используйте:\n"
                f"`/approve {user.id}` - одобрить\n"
                f"`/reject {user.id}` - отклонить"
            )
            
            for admin in admins:
                try:
                    await context.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin.telegram_id}: {e}")
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
                    "Вы не зарегистрированы.\nИспользуйте /start"
                )
                return
            
            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(user.status.value, "❓")
            
            await update.message.reply_text(
                f"*Ваш статус:*\n\n"
                f"Статус: {status_emoji} {user.status.value}\n"
                f"Роль: {user.role.value}\n"
                f"ID: `{user.telegram_id}`\n"
                f"Зарегистрирован: {user.created_at.strftime('%Y-%m-%d %H:%M')}",
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
            
            if not user or user.status != UserStatus.approved:
                await update.message.reply_text(
                    "📚 *Справка*\n\n"
                    "/start - Регистрация\n"
                    "/status - Проверка статуса\n"
                    "/help - Эта справка\n\n"
                    "Ожидайте подтверждения администратора.",
                    parse_mode='Markdown'
                )
                return
            
            # Общие команды
            help_text = "📚 *Справка*\n\n*Общие команды:*\n"
            help_text += "/start - Регистрация\n"
            help_text += "/status - Проверка статуса\n"
            help_text += "/notifications - Настройка уведомлений\n"
            help_text += "/help - Эта справка\n"
            
            # Команды для developer и admin
            if user.role in [UserRole.developer, UserRole.admin]:
                help_text += "\n*Для разработчиков:*\n"
                help_text += "/addapp <bundle_id|app_id> - Добавить приложение\n"
                help_text += "/checkapp <app_id> - Проверить приложение\n"
            
            # Команды для admin
            if user.role == UserRole.admin:
                help_text += "\n*Для администраторов:*\n"
                help_text += "/users - Список пользователей\n"
                help_text += "/approve <id> - Одобрить\n"
                help_text += "/reject <id> - Отклонить\n"
                help_text += "/setrole <id> <role> - Сменить роль\n"
                help_text += "/stats - Статистика\n"
            
            await update.message.reply_text(help_text, parse_mode='Markdown')
        finally:
            db.close()
    
    async def cmd_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /notifications - настройка уведомлений"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not user or user.status != UserStatus.approved:
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
        """Команда /users - список пользователей (admin)"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not user or user.role != UserRole.admin or user.status != UserStatus.approved:
                await update.message.reply_text("❌ Недостаточно прав")
                return
            
            users = db.query(TelegramUser).order_by(TelegramUser.created_at.desc()).limit(20).all()
            
            message = "👥 *Пользователи (последние 20)*\n\n"
            for u in users:
                status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(u.status.value, "❓")
                role_emoji = {"admin": "👑", "developer": "💻", "manager": "👤"}.get(u.role.value, "❓")
                message += f"{status_emoji} {role_emoji} `{u.id}` - @{u.username or 'N/A'} - {u.full_name or 'Без имени'}\n"
            
            message += "\nИспользуйте `/approve <id>`, `/reject <id>`, `/setrole <id> <role>`"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        finally:
            db.close()
    
    async def cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /approve - одобрить пользователя (admin)"""
        telegram_id = str(update.effective_user.id)
        
        db = self._get_db()
        try:
            admin = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
            
            if not admin or admin.role != UserRole.admin or admin.status != UserStatus.approved:
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
            
            user.status = UserStatus.approved
            user.approved_by = admin.id
            user.updated_at = datetime.utcnow()
            db.commit()
            
            # Уведомление пользователя
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"✅ *Заявка одобрена!*\n\nРоль: *{user.role.value}*\n\nИспользуйте /help для списка команд.",
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
            
            if not admin or admin.role != UserRole.admin or admin.status != UserStatus.approved:
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
            
            user.status = UserStatus.rejected
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
            
            if not admin or admin.role != UserRole.admin or admin.status != UserStatus.approved:
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
            
            user.role = UserRole(role_name)
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
            
            if not admin or admin.role != UserRole.admin or admin.status != UserStatus.approved:
                await update.message.reply_text("❌ Недостаточно прав")
                return
            
            total = db.query(TelegramUser).count()
            pending = db.query(TelegramUser).filter(TelegramUser.status == UserStatus.pending).count()
            approved = db.query(TelegramUser).filter(TelegramUser.status == UserStatus.approved).count()
            rejected = db.query(TelegramUser).filter(TelegramUser.status == UserStatus.rejected).count()
            
            admins = db.query(TelegramUser).filter(TelegramUser.role == UserRole.admin).count()
            developers = db.query(TelegramUser).filter(TelegramUser.role == UserRole.developer).count()
            managers = db.query(TelegramUser).filter(TelegramUser.role == UserRole.manager).count()
            
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
