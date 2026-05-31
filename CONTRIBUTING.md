# Contributing to SCOS

First off, thank you for considering contributing to SCOS (Smart Waste Collection Optimization System)! It's people like you that make SCOS such a great tool for modern municipal waste management.

## Where do I go from here?

If you've noticed a bug or have a feature request, make one! It's generally best if you get confirmation of your bug or approval for your feature request this way before starting to code.

## Fork & create a branch

If this is something you think you can fix, then fork SCOS and create a branch with a descriptive name.

A good branch name would be (where issue #325 is the ticket you're working on):

```bash
git checkout -b 325-fix-citizen-login
```

## Get the test suite running

Make sure you're using Python 3.10+ and a virtual environment.
Run the backend server locally to verify your changes:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Implement your fix or feature

At this point, you're ready to make your changes! Feel free to ask for help; everyone is a beginner at first.

## Make a Pull Request

At this point, you should switch back to your master branch and make sure it's up to date with SCOS's master branch:

```bash
git remote add upstream https://github.com/yourusername/SCOS.git
git checkout master
git pull upstream master
```

Then update your feature branch from your local copy of master, and push it!

```bash
git checkout 325-fix-citizen-login
git rebase master
git push --set-upstream origin 325-fix-citizen-login
```

Finally, go to GitHub and make a Pull Request.

## Keeping your Pull Request updated

If a maintainer asks you to "rebase" your PR, they're saying that a lot of code has changed, and that you need to update your branch so it's easier to merge.

Thank you for contributing!
