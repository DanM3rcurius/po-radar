"""poradar: local-first influence-operation radar. `poradar scan` is the hero loop."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .decisions.router import select
from .ingest import fetch_url, item_from_text, poll_feed
from .models import DISCLAIMER, Item, RadarResult
from .questions import BUNDLED, bank_path, bank_status, load_bank
from .store import Store, default_db_path, home_dir

app = typer.Typer(help="Psyop Radar: signals to investigate, not an attribution of intent or actor.",
                  no_args_is_help=True, add_completion=False)
questions_app = typer.Typer(help="Inspect or replace the question bank.")
app.add_typer(questions_app, name="questions")
log_app = typer.Typer(help="Habitual log: dated entries (claim, score, verdict) that build calibrated intuition.")
app.add_typer(log_app, name="log")
VERDICTS = ("organic", "sensationalized", "engineered", "unsure")
console = Console()
err = Console(stderr=True)


def _load_source(source: str) -> Item:
    if source == "-":
        return item_from_text(sys.stdin.read(), origin="stdin")
    if source.startswith(("http://", "https://")):
        return fetch_url(source)
    p = Path(source)
    if not p.exists():
        raise typer.BadParameter(f"{source}: not a file, URL, or '-'")
    return item_from_text(p.read_text(encoding="utf-8", errors="replace"), title=p.stem.replace("_", " "), origin="file")


def _egress_line(route) -> None:
    err.print(f"[dim]egress: {route.egress}  ·  {route.reason}[/dim]")


def _render(r: RadarResult, as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(r.to_json_dict()))
        return
    color = {"quiet": "green", "watch": "yellow", "dense": "dark_orange", "saturated": "red"}[r.band]
    head = f"[bold {color}]{r.band.upper()}[/] ERS {r.ers:.0f}/100 · mode {r.mode} · bank {r.bank}"
    if r.needs_review:
        head += " · [yellow]needs review[/]"
    console.print(Panel(head, title=r.title[:80] or r.item_id, subtitle=f"narrative {r.narrative_id}"))
    t = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    t.add_column("signal")
    t.add_column("value")
    t.add_column("why it matters")
    for e in r.evidence:
        t.add_row(e.signal, str(e.value), e.note)
    console.print(t)
    console.print("[bold]Would lower this:[/]")
    for f in r.falsifiers:
        console.print(f"  · {f}")
    if r.semantic and r.semantic.answers:
        t2 = Table(title=f"decisions via {r.semantic.provider} ({r.semantic.latency_ms} ms{', cached' if r.semantic.cached else ''})",
                   box=None)
        t2.add_column("question")
        t2.add_column("answer")
        t2.add_column("conf")
        t2.add_column("gate")
        for a in r.semantic.answers.values():
            v = f"{float(a.value):.2f}" if a.type == "noul" else (a.label or str(a.value))
            t2.add_row(a.qid, v, f"{a.confidence:.2f}", a.gate)
        console.print(t2)
    if r.worksheet:
        w = r.worksheet
        wt = Table(title=f"NCI-style worksheet: {w.total}/100 · {w.reading} · {w.auto_rows} rows scored from text, {w.human_rows} for you",
                   box=None)
        wt.add_column("#")
        wt.add_column("category")
        wt.add_column("1-5")
        wt.add_column("basis")
        wt.add_column("receipt")
        for row in w.rows:
            wt.add_row(str(row.n), row.category, str(row.score), row.basis, row.receipt[:90])
        console.print(wt)
    if r.define_first:
        console.print("[bold]Define first (Deep Truth Mode):[/] " + ", ".join(r.define_first))
    if r.brief:
        console.print(Panel(r.brief, title="brief"))
    console.print(f"[dim]{DISCLAIMER}[/dim]")


@app.command()
def scan(
    source: str = typer.Argument(..., help="file path, URL, or '-' for stdin"),
    cloud: bool = typer.Option(False, "--cloud", help="allow Jev via TypeSafe/OpenRouter (needs a key in env)"),
    allow_stdin_egress: bool = typer.Option(False, "--allow-stdin-egress", help="let stdin text reach a cloud provider"),
    offline: bool = typer.Option(False, "--offline", help="no network at all: lexical-only mode"),
    no_brief: bool = typer.Option(False, "--no-brief", help="skip the brief"),
    as_json: bool = typer.Option(False, "--json"),
    save: bool = typer.Option(False, "--save", help="persist to the local radar store"),
) -> None:
    """Scan one item. Works with zero keys and no network."""
    from .pipeline import run

    item = _load_source(source)
    if item.ingest_rejected:
        err.print(f"[red]ingest rejected:[/] {item.ingest_reason}")
        raise typer.Exit(2)
    route = select(cloud=cloud, origin=item.origin, allow_stdin_egress=allow_stdin_egress, offline=offline)
    _egress_line(route)
    store = Store() if save else None
    results = asyncio.run(run([item], route=route, store=store, brief=not no_brief,
                              use_local_model_for_brief=not offline))
    for r in results:
        _render(r, as_json)


@app.command()
def watch(
    feeds: list[str] = typer.Argument(None, help="feed URLs; defaults to ~/.poradar/feeds.txt"),
    cloud: bool = typer.Option(False, "--cloud"),
    offline: bool = typer.Option(False, "--offline"),
    once: bool = typer.Option(True, "--once/--loop", help="poll once (default) or loop"),
    interval: int = typer.Option(900, help="seconds between polls when looping"),
    no_brief: bool = typer.Option(False, "--no-brief"),
) -> None:
    """Poll feeds into the local store, cluster, score. Feed health is tracked per URL."""
    import time

    from .pipeline import run

    if not feeds:
        f = home_dir() / "feeds.txt"
        if not f.exists():
            err.print(f"no feeds given and {f} does not exist")
            raise typer.Exit(2)
        feeds = [ln.strip() for ln in f.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    store = Store()
    route = select(cloud=cloud, origin="feed", offline=offline)
    _egress_line(route)
    while True:
        fresh: list[Item] = []
        for url in feeds:
            items, status = poll_feed(url)
            if status != "ok":
                store.feed_fail(url, status)
                err.print(f"[yellow]{url}[/]: {status}")
                continue
            new = [i for i in items if not store.has_item(i.id)]
            store.feed_ok(url, len(new))
            for i in items:
                if i.ingest_rejected:
                    store.put_item(i.model_dump(mode="json"))
            fresh.extend(i for i in new if not i.ingest_rejected)
            err.print(f"{url}: {len(items)} entries, {len(new)} new, {sum(1 for i in items if i.ingest_rejected)} rejected")
        if fresh:
            results = asyncio.run(run(fresh, route=route, store=store, brief=not no_brief,
                                      use_local_model_for_brief=not offline))
            console.print(f"scored {len(results)} items; top: " + ", ".join(f"{r.band} {r.ers:.0f}" for r in results[:5]))
        if once:
            break
        time.sleep(interval)


@app.command()
def report(limit: int = 20, as_json: bool = typer.Option(False, "--json")) -> None:
    """Top narratives from the local store, plus feed health."""
    store = Store()
    rows = store.recent(limit=500)
    if as_json:
        console.print_json(json.dumps({"results": rows[:limit], "feeds": store.feeds(), "disclaimer": DISCLAIMER}))
        return
    by_n: dict[str, list[dict]] = {}
    for r in rows:
        by_n.setdefault(r["narrative_id"], []).append(r)
    t = Table(title="narratives by signal density", box=None)
    t.add_column("band")
    t.add_column("ERS")
    t.add_column("items")
    t.add_column("mode")
    t.add_column("title")
    t.add_column("would lower this")
    ranked = sorted(by_n.values(), key=lambda g: max(x["ers"] for x in g), reverse=True)[:limit]
    for g in ranked:
        top = max(g, key=lambda x: x["ers"])
        t.add_row(top["band"], f"{top['ers']:.0f}", str(len(g)), top["mode"], top["title"][:60], top["falsifiers"][0][:60])
    console.print(t)
    feeds = store.feeds()
    if feeds:
        ft = Table(title="feed health", box=None)
        ft.add_column("feed")
        ft.add_column("last success")
        ft.add_column("status")
        ft.add_column("fails")
        ft.add_column("dead")
        for f in feeds:
            ft.add_row(f["url"][:60], (f["last_success"] or "never")[:19], f["last_status"] or "", str(f["consecutive_failures"]), "yes" if f["dead"] else "")
        console.print(ft)
    console.print(f"[dim]{DISCLAIMER}[/dim]")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8642) -> None:
    """Local radar dashboard (binds localhost only by default)."""
    from .server import run as run_server

    console.print(f"radar at http://{host}:{port}  ·  store {default_db_path()}")
    run_server(host=host, port=port)


@app.command()
def doctor() -> None:
    """What is live, what would leave the machine. Never prints secrets."""
    from .decisions.ollama import ollama_url, reachable

    t = Table(title=f"poradar {__version__}", box=None)
    t.add_column("check")
    t.add_column("status")
    has_ts = bool(os.environ.get("TYPESAFE_API_KEY"))
    has_or = bool(os.environ.get("OPENROUTER_API_KEY"))
    t.add_row("TYPESAFE_API_KEY", "set" if has_ts else "not set")
    t.add_row("OPENROUTER_API_KEY", "set" if has_or else "not set")
    t.add_row("PORADAR_ALLOW_CLOUD", os.environ.get("PORADAR_ALLOW_CLOUD", "unset (cloud off; pass --cloud per run)"))
    t.add_row("Ollama", f"{ollama_url()} " + ("reachable" if reachable() else "not reachable"))
    t.add_row("default route", select(probe=reachable).reason)
    t.add_row("cloud route (if --cloud)", select(cloud=True, probe=reachable).reason)
    t.add_row("question bank", f"{bank_path()} ({bank_status()})")
    t.add_row("store", str(default_db_path()))
    t.add_row("evaluate (MCP adapter)", shutil.which("evaluate") or "not on PATH (docs/JEV_SETUP.md)")
    console.print(t)
    store = Store()
    feeds = store.feeds()
    if feeds:
        dead = [f for f in feeds if f["dead"]]
        console.print(f"feeds: {len(feeds)} tracked, {len(dead)} dead")


@app.command()
def dryrun(
    cloud: bool = typer.Option(False, "--cloud", help="make one real Jev call (needs a key in env)"),
    fixture: Path = typer.Option(None, help="text file to use; defaults to a bundled fixture"),
) -> None:
    """One reversible decision call on a bundled fixture. Writes nothing. Without --cloud uses the stub."""
    from .decisions.stub import StubProvider
    from .semantic import evaluate_item

    path = fixture or (Path(__file__).parents[2] / "tests" / "fixtures" / "outrage_bait.txt")
    if not path.exists():
        err.print(f"fixture not found: {path}")
        raise typer.Exit(2)
    item = item_from_text(path.read_text(encoding="utf-8"), title=path.stem, origin="file")
    if cloud:
        route = select(cloud=True, origin="file")
        if route.provider is None:
            err.print(route.reason)
            raise typer.Exit(2)
        provider, egress = route.provider, route.egress
    else:
        provider, egress = StubProvider(), "none"
    err.print(f"[dim]egress: {egress} · provider {provider.name} · fixture {path.name}[/dim]")
    res = asyncio.run(evaluate_item(item, provider, egress, store=None))
    t = Table(title=f"{res.provider} answered in {res.latency_ms} ms", box=None)
    t.add_column("question")
    t.add_column("answer")
    t.add_column("conf")
    t.add_column("gate")
    for a in res.answers.values():
        v = f"{float(a.value):.2f}" if a.type == "noul" else (a.label or str(a.value))
        t.add_row(a.qid, v, f"{a.confidence:.2f}", a.gate)
    console.print(t)


@log_app.command("add")
def log_add(
    claim: str = typer.Argument(..., help="the core claim, in your words"),
    verdict: str = typer.Option(..., "--verdict", help="organic | sensationalized | engineered | unsure"),
    summary: str = typer.Option(None, help="one-line summary"),
    item: str = typer.Option(None, "--item", help="item id from a --save scan, to attach its scores"),
    notes: str = typer.Option(None, help="receipts, sources read, what would change your mind"),
    date: str = typer.Option(None, help="ISO date/time; defaults to now (UTC)"),
) -> None:
    """Write one dated entry. The date is the point: patterns show up across months, not days."""
    if verdict not in VERDICTS:
        raise typer.BadParameter(f"verdict must be one of {VERDICTS}")
    store = Store()
    ers = wt = band = None
    if item:
        res = store.get(item)
        if not res:
            err.print(f"no saved result for item {item}; run `poradar scan ... --save` first")
            raise typer.Exit(2)
        ers, band = res["ers"], res["band"]
        wt = (res.get("worksheet") or {}).get("total")
    n = store.log_add(claim=claim, verdict=verdict, summary=summary, item_id=item, ers=ers, worksheet_total=wt,
                      band=band, notes=notes, logged=date)
    console.print(f"logged entry #{n} ({verdict}) at {date or 'now'}")


@log_app.command("show")
def log_show(limit: int = 50) -> None:
    """Dated entries, newest first."""
    rows = Store().log_entries(limit)
    t = Table(title="habitual log", box=None)
    for c in ("date", "verdict", "ERS", "NCI", "claim"):
        t.add_column(c)
    for r in rows:
        t.add_row(r["logged"][:16], r["verdict"], "" if r["ers"] is None else f"{r['ers']:.0f}",
                  "" if r["worksheet_total"] is None else str(r["worksheet_total"]), r["claim"][:70])
    console.print(t)
    if rows:
        by = {}
        for r in rows:
            by[r["verdict"]] = by.get(r["verdict"], 0) + 1
        console.print("[dim]" + ", ".join(f"{k}: {v}" for k, v in sorted(by.items())) + "[/dim]")


@log_app.command("export")
def log_export(path: Path = typer.Argument(Path("poradar-log.csv"))) -> None:
    """CSV of the log (your notebook, your machine)."""
    import csv

    rows = Store().log_entries(100000)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["logged", "verdict", "ers", "worksheet_total", "band", "claim", "summary", "item_id", "notes"])
        for r in rows:
            w.writerow([r["logged"], r["verdict"], r["ers"], r["worksheet_total"], r["band"], r["claim"], r["summary"], r["item_id"], r["notes"]])
    console.print(f"wrote {len(rows)} entries to {path}")


@questions_app.command("show")
def questions_show() -> None:
    """Print the active question bank and where it was loaded from."""
    p = bank_path()
    err.print(f"[dim]{p} ({bank_status()})[/dim]")
    console.print_json(json.dumps(load_bank(str(p))))


@questions_app.command("import")
def questions_import(file: Path) -> None:
    """Install a replacement bank at ~/.poradar/questions.json (validated first)."""
    load_bank(str(file))  # raises with a path if malformed
    dest = home_dir() / "questions.json"
    shutil.copyfile(file, dest)
    console.print(f"installed {dest}; status now {bank_status(str(dest))}. Bundled default stays at {BUNDLED}")


@questions_app.command("reset")
def questions_reset() -> None:
    """Remove the user bank; fall back to the bundled provisional one."""
    dest = home_dir() / "questions.json"
    if dest.exists():
        dest.unlink()
        console.print(f"removed {dest}")
    else:
        console.print("no user bank installed")


if __name__ == "__main__":
    app()
