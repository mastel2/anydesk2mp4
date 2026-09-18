# Privacy Policy — Recording Converter for AnyDesk

**Last updated: 19 September 2026**

Recording Converter for AnyDesk is made by KEEP_DARK. This policy explains what the
program does with your data. The short version: everything happens on your own PC, and
nothing is sent anywhere.

## What the program collects

**Nothing.** There is no account, no sign-in, no analytics, no telemetry, no crash
reporting and no advertising. The program has no code that opens a network connection,
and it does not contain any third-party SDK that could.

## What the program reads on your PC

- **The recordings you choose.** Only the files you add to the queue. It reads the file
  header to show who connected, the screen size and the length, and it asks your own
  AnyDesk client to play the file so the picture can be recorded.
- **AnyDesk's local log file** (`%APPDATA%\AnyDesk\ad.trace`). It is read to confirm
  that the player accepted a "restart playback" command. Nothing from it is stored or
  sent.
- **Its own settings and queue** (`%APPDATA%\anydesk2mp4\`). Your chosen format,
  quality, language, theme, output folder and the list of files waiting to convert.

## What the program writes

- **The converted video**, in the folder you pick.
- **Its own settings and queue**, in the folder above.
- A temporary working file next to the video while a conversion runs; it is deleted when
  the conversion finishes.

## Session recordings contain other people's screens

A recording shows whatever was on the remote screen: documents, messages, personal
details. The program never inspects, uploads or shares that content — but you should
make sure you are allowed to keep and pass on the recordings you convert, and that the
people involved knew the session was recorded. Where you are, that may be a legal
requirement rather than a courtesy.

## Third-party components

- **FFmpeg** (LGPL v3), bundled unmodified and run as a separate program on your PC to
  write the video file. It makes no network connections in the way this program uses it.
- **AnyDesk**, which you install and control yourself. The program starts your AnyDesk
  client to play your own recordings. It does not contain, modify or redistribute any
  AnyDesk software, and it is not affiliated with AnyDesk Software GmbH.

## Children

The program is a tool for handling your own files and is not directed at children.

## Changes

If this policy changes, the new version will be published at this address and the date
at the top will be updated.

## Contact

Questions about this policy: **https://www.keep-dark.com/works/**
