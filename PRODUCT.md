# Círculo

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript and a local Python + Playwright runner, as specified in the supplied plan. SQLite stores resumable execution. Local delivery; no hosted service is needed for this first version.

## Users

The owner of Instagram, TikTok and Facebook accounts, starting with David on this Windows computer. Other users should be able to run their own copy.

## Product Purpose

Compare exported following and followers lists, select accounts that do not follow back, then execute a reviewed unfollow queue from the user's own browser session.

## Operating Context

User confirmed Windows and the default criterion: only accounts that do not follow back. UI is in Spanish. The supplied conversation establishes local execution and no password collection.

## Capabilities and Constraints

Start with Instagram. Keep modular adapters for TikTok and Facebook. Import, preview, selection, exclusions, targets.json export, persistent queue, dry run, daily limits, pause and stop on challenge. Instagram and TikTok adapters validated in a real authenticated session; Facebook remains beta. Distribution: free public web analyzer (davidcevallos.me/circulo/app/, served by Vercel from personal_web), free Windows portable build (GitHub Releases, linked from davidcevallos.me/circulo/descargar/), and Círculo Pro reservation ($9 USD) for support and upcoming features.

## Evidence on Hand

Source code in this repository, QA screenshots in .impeccable/review, demo video in presentacion/. Real exports and sessions stay on the owner's machine only.

## Product Principles

- Account lists remain local.
- Show known and unknown follow-back states separately.
- Clearly distinguish example data, simulation and actual execution.
- Confirm an action from observed state before recording success.
