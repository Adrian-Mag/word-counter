# ✍️ WordCounter

A simple, cute desktop app for tracking your daily writing progress.

![Icon](assets/icon.svg)

## Features

- **Quick word logging** — Enter how many words you wrote, hit Enter. Log multiple times per day; each entry adds to your daily total.
- **Today's summary** — See today's word count, current streak, all-time total, and entry count at a glance.
- **Statistics dashboard** — Beautiful bar charts showing daily word counts over the past week, month, or 6 months. Includes averages, best day, streaks, and more.
- **Automatic backups** — Every entry is saved to a local database AND backed up to JSON files automatically.
- **No account needed** — All data stays on your computer. Nothing is uploaded anywhere.

## 📥 Install (for non-coders)

### Windows
1. Go to the [Releases page](../../releases)
2. Download **WordCounter.exe**
3. Save it to your Desktop (or anywhere you like)
4. Double-click to run — that's it! No installation required.

> If Windows SmartScreen warns you, click **"More info"** → **"Run anyway"**. This is normal for apps that aren't code-signed.

### Run from source (for developers)
```bash
# Create conda environment
conda create -n word-counter-dev python=3.11 -y
conda activate word-counter-dev
pip install -r requirements.txt

# Run the app
python -m word_counter
```

## 🖼️ What it looks like

The app opens to a clean input screen where you log your words. Click **"View Statistics"** to see charts and detailed stats.

## 📊 Stats included

- Daily word count bar charts (past week / month / 6 months)
- Average words per day
- Best writing day
- Current writing streak (consecutive days with words)
- All-time total word count
- Total number of entries
- Recent entries log with timestamps and notes

## 💾 Data & Backups

Your writing data is stored in:
- **Database**: `%APPDATA%\WordCounter\wordcounter.db` (SQLite)
- **Backups**: `%APPDATA%\WordCounter\backups\` (JSON files — latest + last 10 timestamped backups)

You can safely copy the backup JSON files to another computer.

## 🔧 Building from source

```bash
# Install build dependencies
pip install PyQt5 matplotlib pyinstaller

# Build the .exe
pyinstaller word_counter.spec --noconfirm
```

The executable will be in `dist/WordCounter.exe`.

## 🚀 Creating a new release

Maintainers can create a new release by tagging a version:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This triggers GitHub Actions to automatically build the Windows executable and create a GitHub Release with the `.exe` attached.

## License

MIT
