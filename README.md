# 🤖 Assign Bot

A sophisticated Telegram bot for automated team task assignments with flexible participant management, multiple selection strategies, and seamless workflow integration.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.13+-blue?style=for-the-badge&logo=python)
![aiogram](https://img.shields.io/badge/aiogram-3.x-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

</div>

## ✨ Features

### 🎯 **Smart Assignment System**
- **Multiple Selection Policies**: Choose between Round-Robin (fair rotation) or Random assignment
- **Flexible Team Size**: Assign 1, 2, or 3 participants per task automatically
- **Active Participant Selection**: Easy checkbox interface to exclude unavailable team members
- **State Persistence**: Round-robin maintains position across sessions

### 👥 **Advanced User Management**
- **Admin Control**: Role-based permissions for participant configuration
- **Default Participants**: Pre-configured team list for quick setup
- **Dynamic Teams**: Real-time participant availability management
- **User ID Discovery**: Built-in `/myid` command for easy admin setup

### 📡 **Seamless Integration**
- **Channel Broadcasting**: Automatic assignment posts to designated channels
- **Interactive Polls**: Built-in completion tracking with checkbox polls
- **@Mention Notifications**: Direct participant tagging for immediate alerts
- **Custom Descriptions**: Rich task descriptions with links and instructions

### 🛡️ **Security & Configuration**
- **Environment-based Setup**: Secure configuration via environment variables
- **Multiple Admin Support**: Configure multiple administrators
- **Flexible Channel Setup**: Support for numeric IDs and usernames
- **Graceful Error Handling**: Robust error management and user feedback

## 🚀 Quick Start

### Prerequisites
- Python 3.13.6+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Target channel/chat for assignments

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd assign-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r pyproject.toml
   # or using uv
   uv sync
   ```

3. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. **Run the bot**
   ```bash
   python main.py
   ```

## ⚙️ Configuration

Create a `.env` file with the following variables:

```env
# Required: Your Telegram Bot Token
BOT_TOKEN=your_bot_token_here

# Required: Admin User IDs (comma or space separated)
ADMIN_USER_ID=123456789,987654321

# Required: Target channel for assignments
ASSIGN_CHANNEL_ID=@yourchannel
# Or use numeric ID: ASSIGN_CHANNEL_ID=-1001234567890
```

### Getting Your User ID
1. Start the bot and send `/myid`
2. Copy your User ID to the `ADMIN_USER_ID` environment variable

### Channel Setup
- **For public channels**: Use `@channelname` format
- **For private channels**: Use numeric ID (forward a message to [@userinfobot](https://t.me/userinfobot))
- Ensure the bot is added to the channel with posting permissions

## 📋 Usage Guide

### Basic Workflow

1. **Start the bot**
   ```
   /start
   ```

2. **Configure your team** (Admin only)
   ```
   /configure
   ```
   Or use the "Configure Participants" button and enter usernames:
   ```
   @alice @bob @charlie @david
   ```

3. **Create assignment**
   ```
   /assign
   ```
   Or use the "Assign Participants" button and follow the interactive flow:
   - ✅ Select active participants (checkbox interface)
   - 🔄 Choose assignment policy (Round-Robin or Random)
   - 🔢 Select number of assignees (1, 2, or 3)
   - 📝 Enter task description
   - 🎯 Assignment posted to configured channel with completion poll

### Available Commands

| Command | Description | Access |
|---------|-------------|---------|
| `/start` | Show welcome message and main menu | Everyone |
| `/configure` | Set up team participants list | Admins only |
| `/assign` | Create new task assignment | Everyone |
| `/myid` | Display your User ID for admin setup | Everyone |

## 🏗️ Architecture

### Project Structure
```
assign-bot/
├── src/assign_bot/
│   ├── bot.py          # Main bot logic and handlers
│   ├── selector.py     # Selection strategies and policies
│   └── __init__.py     # Module exports
├── tests/              # Comprehensive test suite
├── main.py            # Application entry point
├── pyproject.toml     # Dependencies and metadata
└── env.example        # Configuration template
```

### Core Components

- **Bot Module** (`bot.py`): Telegram bot handlers, user management, and workflow orchestration
- **Selector Module** (`selector.py`): Pluggable selection strategies with state management
- **Strategy Pattern**: Clean separation between Random and Round-Robin selection logic
- **State Management**: In-memory state with planned persistent storage support

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/assign_bot

# Run specific test categories
pytest tests/test_selector.py          # Selector logic tests
pytest tests/test_bot_integration.py   # Bot integration tests
```

Test coverage includes:
- ✅ Selection strategy algorithms
- ✅ Bot workflow integration
- ✅ Error handling scenarios
- ✅ Real-world usage patterns

## 🔧 Advanced Configuration

### Multiple Administrators
```env
# Multiple ways to specify admin IDs
ADMIN_USER_ID=123456789,987654321,555666777
# or
ADMIN_USER_ID=123456789 987654321 555666777
```

### Channel Configuration Examples
```env
# Public channel with username
ASSIGN_CHANNEL_ID=@myteamchannel

# Private channel with numeric ID
ASSIGN_CHANNEL_ID=-1001234567890

# Channel username without @
ASSIGN_CHANNEL_ID=myteamchannel
```

## 🎯 Use Cases

- **Daily Standups**: Rotate meeting facilitators fairly
- **Code Reviews**: Distribute review assignments across team
- **Support Duty**: Assign support rotations with vacation handling
- **Task Distribution**: Random or fair assignment of project tasks
- **Event Organization**: Assign event planning responsibilities

## 🛠️ Development

### Local Development Setup
```bash
# Install development dependencies
uv sync --dev

# Run linting
ruff check src/ tests/

# Run type checking  
mypy src/

# Run tests with watch mode
pytest-watch
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Documentation**: Check the code comments and test files for detailed usage examples
- **Community**: Join discussions in the project's GitHub Discussions section