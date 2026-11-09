# beep-beginners

A setup for people who use Claude every day but have never worked in a code
repository. Claude gets the same things a software engineer gets from a
well-run project: a history of every change, backups, safety rails, notes
that last, a way to think ideas through, and a caretaker that tidies up while
you're away. You don't need to learn any of it. You start Claude and ask for
things.

## Getting set up

1. Open the Claude app and switch to **Code** (the `</>` button at the top left).
2. Pick any empty folder (make one on the Desktop called `setup`).
3. Paste this and press Enter:

> Set up this computer with the beep-beginners kit. In PowerShell, run
> irm https://raw.githubusercontent.com/kriegcloud/beep-beginners/main/bootstrap.ps1 | iex
> and then follow the onboarding skill from step 1.

Claude explains each step before it does it. You'll type your own passwords,
approve sign-in codes, click **Add** once in Chrome, click **Install** once on
GitHub, and click **Yes** once on a Windows permission box. Near the start,
Claude asks you to paste your Claude memories so it can learn how you work.
You can stop at any point. Saying "keep setting me up" picks up where it
left off. Setup ends with Claude starting on the first thing you said you
wanted to figure out.

## After setup

Open the Claude app, choose **Code**, and pick your workspace folder. Then
ask in plain words:

- "I want to explore starting a side business" thinks an idea through with you
  and writes it up.
- "Build me a tool that ..." makes a project with its own tests and checks.
- "What needs me?" goes through anything the caretaker couldn't decide alone.
- "Teach me what you just did" explains the last thing Claude did, as a short
  lesson.
- "I need help" writes down what broke and tells you to text your helper.
- "Stop my helper's access" turns off your helper's remote access. You can
  use their name instead.

Four commands are worth typing:

- `/grill-me` asks you hard questions about a plan until it holds up.
- `/teach` gives you a lesson on any topic, at your pace.
- `/handoff` wraps up a session so the next one can pick it up.
- `/wait-what` when something didn't make sense.

Everything is saved to your private GitHub account at the end of every
session. Every morning a caretaker checks your workspace, merges finished
work whose checks passed, reads security notices, and writes anything it
couldn't decide into a page called NEEDS-YOU, which Claude reads to you at
the start of your next session. The caretaker runs on your Claude
subscription, so a busy week uses a little more of it. Updates to this kit
arrive by themselves.

## For maintainers

See [docs/MAINTAINING.md](docs/MAINTAINING.md) and
[docs/DECISIONS.md](docs/DECISIONS.md).
