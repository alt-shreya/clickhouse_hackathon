from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_summary_dashboard(
    feature_name: str, ddl: str, context_diff: str, insight: str
):
    console.print(
        Panel.fit(
            f"[bold cyan]Pipeline Summary for {feature_name}[/bold cyan]",
            border_style="green",
        )
    )

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Stage", style="dim", width=20)
    table.add_column("Status", justify="left")

    table.add_row(
        "Instrumentation Agent", "[green]DDL Executed Successfully[/green]"
    )
    table.add_row("Context Agent", "[green]Context Updated[/green]")
    table.add_row(
        "Analytics Agent", "[green]Insight Summary Generated[/green]"
    )

    console.print(table)
    console.print(
        Panel(
            insight,
            title="Product Insight Summary",
            border_style="yellow",
            expand=False,
        )
    )