# Assign Bot

Assign Bot is a Telegram bot that simplifies team task assignments with just two buttons: **Configure Participants** and **Assign Participants**.

## 🚀 Features
- **Two-Button Interface**  
  1. **Configure Participants** – enter Telegram usernames of your team.  
  2. **Assign Participants** – select who’s active for this round via checkboxes (exclude yourself, people on vacation, etc.).
- **Selection Policy**  
  – Choose between **Round-Robin** or **Random** assignment.  
- **Custom Description**  
  – Enter any text (task details, links, instructions) in a description field.  
- **Notification & Poll**  
  – Specify a target Telegram channel. Bot sends a message tagging assigned users, includes your custom description, and creates a checkbox poll so assignees can mark “✔️ Done.”

## ⚙️ Usage Flow
1. Press **Configure Participants**  
   - Input list of `@usernames`  
2. Press **Assign Participants**  
   - Check ✔️ next to active users (excludes)  
   - Select **Round-Robin** or **Random**  
   - Enter a **Description** (task details, URLs)  
   - Choose **Target Channel** for notification  
3. Bot posts assignment to channel:  
   - Tagged assignees  
   - Your description  
   - Checkbox poll for completion