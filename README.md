# beep-beginners

A setup for people who use Claude every day but have never worked in a code
repository. Claude gets the same things a software engineer gets from a
well-run project: a history of every change, backups, safety rails, notes
that last, and a way to think ideas through. You don't need to learn any of
it. You start Claude and ask for things.

## Getting set up

1. Open the Claude app and switch to **Code**.
2. Pick any empty folder (make one on the Desktop called `setup`).
3. Paste this and press Enter:

> Set up this computer with the beep-beginners kit. Install Claude Code with
> the official installer from claude.ai/install.ps1, then install git and uv
> with winget. Then run `claude plugin marketplace add kriegcloud/beep-beginners`
> and `claude plugin install onboarding@beep-beginners --scope user`, and
> follow the onboarding skill from step 1.

Claude explains each step before it does it. You'll type your own passwords,
approve sign-in codes, click **Add** once in Chrome, and click **Yes** once on
a Windows permission box. You can stop at any point. Saying "keep setting me
up" picks up where it left off.

## After setup

Open the Claude app, choose **Code**, and pick your workspace folder. Then
ask in plain words:

- "I want to explore starting a side business" thinks an idea through with you
  and writes it up.
- "Teach me what you just did" explains the last thing Claude did, as a short
  lesson.
- "I need help" writes down what broke and tells you to text your helper.
- "Stop my helper's access" turns off your helper's remote access. You can
  use their name instead.

Two commands are worth typing:

- `/grill-me` asks you hard questions about a plan until it holds up.
- `/teach` gives you a lesson on any topic, at your pace.

Everything is saved to your private GitHub account at the end of every
session. Updates to this kit arrive by themselves.

## For maintainers

See [docs/MAINTAINING.md](docs/MAINTAINING.md) and
[docs/DECISIONS.md](docs/DECISIONS.md).
