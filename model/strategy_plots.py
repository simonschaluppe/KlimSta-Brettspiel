import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

from model.plotting import (
    PLOT_STYLE,
    canonical_category,
    category_color,
    category_label,
)


STRATEGY_ORDER = [
    "random",
    "electrician",
    "decarbonizer",
    "insulator",
]

STRATEGY_LABELS = {
    "random": "Random",
    "electrician": "Electrician",
    "decarbonizer": "Decarbonizer",
    "insulator": "Insulator",
}


def strategy_label(strategy):
    return STRATEGY_LABELS.get(
        strategy,
        str(strategy).replace("_", " ").title(),
    )


def ordered_strategies(data):
    present = list(pd.unique(data["strategy"]))

    return [
        strategy
        for strategy in STRATEGY_ORDER
        if strategy in present
    ] + [
        strategy
        for strategy in present
        if strategy not in STRATEGY_ORDER
    ]


def strategy_colors(strategies):
    """
    Stable colors from the active matplotlib cycle.

    Category colors remain reserved for technology categories.
    """
    cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    return {
        strategy: cycle[i % len(cycle)]
        for i, strategy in enumerate(strategies)
    }


def plot_strategy_distribution_facets(
    games,
    metric="vp",
    *,
    xlabel=None,
    title=None,
    bins=35,
    density=True,
    reference=None,
    figsize=None,
):
    """
    One distribution facet per strategy with shared x/y axes.

    Outline histograms keep the figure light and make direct comparison easier.
    """
    strategies = ordered_strategies(games)
    colors = strategy_colors(strategies)

    values = games[metric].dropna()
    bin_edges = np.linspace(
        values.min(),
        values.max(),
        bins + 1,
    )

    fig, axes = plt.subplots(
        1,
        len(strategies),
        figsize=figsize or (3.0 * len(strategies), 3.2),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    axes = axes[0]

    for ax, strategy in zip(axes, strategies):
        data = games.loc[
            games["strategy"] == strategy,
            metric,
        ].dropna()

        ax.hist(
            data,
            bins=bin_edges,
            density=density,
            histtype="step",
            linewidth=1.6,
            color=colors[strategy],
        )

        ax.axvline(
            data.mean(),
            linewidth=1.0,
            linestyle="--",
            color=colors[strategy],
        )

        if reference is not None:
            ax.axvline(
                reference,
                linewidth=0.8,
                linestyle=":",
            )

        ax.set_title(strategy_label(strategy))
        ax.grid(axis="y", alpha=PLOT_STYLE["grid_alpha"])

    fig.supxlabel(xlabel or metric.replace("_", " ").title())
    fig.supylabel("Density" if density else "Games")

    if title:
        fig.suptitle(title)

    fig.tight_layout()

    return fig, axes


def plot_strategy_outcome_facets(
    games,
    metrics,
    *,
    strategy_order=None,
    labels=None,
    title=None,
    figsize=(10, 7),
):
    """
    Compact 2x2-style overview of strategy outcomes.

    Each facet contains one metric with one boxplot per strategy.
    """
    strategies = strategy_order or ordered_strategies(games)
    colors = strategy_colors(strategies)
    labels = labels or {}

    n = len(metrics)
    ncols = 2
    nrows = int(np.ceil(n / ncols))

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=figsize,
        squeeze=False,
    )

    axes_flat = axes.flatten()

    for ax, metric in zip(axes_flat, metrics):
        groups = [
            games.loc[
                games["strategy"] == strategy,
                metric,
            ].dropna()
            for strategy in strategies
        ]

        box = ax.boxplot(
            groups,
            labels=[
                strategy_label(strategy)
                for strategy in strategies
            ],
            patch_artist=True,
            showfliers=False,
            medianprops={"color": "black"},
        )

        for patch, strategy in zip(box["boxes"], strategies):
            patch.set_facecolor(colors[strategy])
            patch.set_alpha(0.55)

        ax.set_title(labels.get(metric, metric.replace("_", " ").title()))
        ax.grid(axis="y", alpha=PLOT_STYLE["grid_alpha"])
        plt.setp(
            ax.get_xticklabels(),
            rotation=45,
            ha="right",
        )

    for ax in axes_flat[n:]:
        ax.set_visible(False)

    if title:
        fig.suptitle(title)

    fig.tight_layout()

    return fig, axes


def plot_strategy_heatmap(
    table,
    *,
    title,
    colorbar_label,
    center=None,
    cmap="viridis",
    figsize=None,
    row_colors=None,
):
    """
    Generic publication-style heatmap.

    `table` must have display-ready row labels and strategy columns.
    """
    values = table.to_numpy(dtype=float)

    if center is None:
        norm = None
    else:
        distance = np.nanmax(np.abs(values - center))
        norm = TwoSlopeNorm(
            vmin=center - distance,
            vcenter=center,
            vmax=center + distance,
        )

    fig, ax = plt.subplots(
        figsize=figsize or (
            max(6, 1.4 * len(table.columns)),
            max(5, 0.28 * len(table.index)),
        )
    )

    image = ax.imshow(
        values,
        aspect="auto",
        cmap=cmap,
        norm=norm,
    )

    ax.set_xticks(range(len(table.columns)))
    ax.set_xticklabels([
        strategy_label(column)
        for column in table.columns
    ])

    ax.set_yticks(range(len(table.index)))
    ax.set_yticklabels(table.index)

    if row_colors is not None:
        for tick, color in zip(ax.get_yticklabels(), row_colors):
            tick.set_color(color)

    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_title(title)

    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(colorbar_label)

    fig.tight_layout()

    return fig, ax


def card_strategy_table(
    card_results,
    metric,
    *,
    card_info=None,
    strategy_order=None,
):
    """
    Cards x strategies matrix, ordered by category and English card name.
    """
    strategies = (
        strategy_order
        or ordered_strategies(card_results)
    )

    table = card_results.pivot_table(
        index="card",
        columns="strategy",
        values=metric,
        aggfunc="mean",
    )

    table = table.reindex(columns=strategies)

    if card_info is None:
        info = (
            card_results[
                ["card", "label_en", "category"]
            ]
            .drop_duplicates("card")
            .set_index("card")
        )
    else:
        info = (
            card_info[
                ["card", "label_en", "category"]
            ]
            .drop_duplicates("card")
            .set_index("card")
        )

    info["_category"] = info["category"].apply(
        canonical_category
    )

    order = (
        info
        .sort_values(["_category", "label_en"])
        .index
        .intersection(table.index)
    )

    table = table.loc[order]
    info = info.loc[order]

    table.index = info["label_en"]

    row_colors = [
        category_color(category)
        for category in info["_category"]
    ]

    return table, row_colors


def plot_card_strategy_heatmap(
    card_results,
    metric,
    *,
    card_info=None,
    title=None,
    colorbar_label=None,
    center=None,
    cmap="viridis",
    figsize=None,
):
    """
    Card x strategy heatmap with category-colored card labels.
    """
    table, row_colors = card_strategy_table(
        card_results,
        metric,
        card_info=card_info,
    )

    return plot_strategy_heatmap(
        table,
        title=title or metric.replace("_", " ").title(),
        colorbar_label=(
            colorbar_label
            or metric.replace("_", " ").title()
        ),
        center=center,
        cmap=cmap,
        figsize=figsize,
        row_colors=row_colors,
    )


def plot_card_strategy_facets(
    card_results,
    metric,
    *,
    card_info=None,
    baseline=None,
    xlabel=None,
    title=None,
    figsize=None,
):
    """
    Facet grid: rows = technology categories, columns = strategies.

    Horizontal outline bars use a shared x axis. This is suited to detailed
    card comparisons where a heatmap would hide the magnitude scale.
    """
    strategies = ordered_strategies(card_results)

    if card_info is None:
        info = (
            card_results[
                ["card", "label_en", "category"]
            ]
            .drop_duplicates("card")
        )
    else:
        info = card_info[
            ["card", "label_en", "category"]
        ].drop_duplicates("card")

    info = info.copy()
    info["_category"] = info["category"].apply(
        canonical_category
    )

    categories = list(dict.fromkeys(info["_category"]))

    nrows = len(categories)
    ncols = len(strategies)

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=figsize or (
            2.7 * ncols,
            max(8, 1.7 * nrows),
        ),
        sharex=True,
        squeeze=False,
    )

    values = card_results[metric].dropna()

    if baseline is None:
        xmin = min(0, values.min())
        xmax = values.max()
    else:
        spread = max(
            abs(values.min() - baseline),
            abs(values.max() - baseline),
        )
        xmin = baseline - spread
        xmax = baseline + spread

    for row, category in enumerate(categories):
        cards = (
            info.loc[
                info["_category"] == category
            ]
            .sort_values("label_en")
        )

        card_ids = cards["card"].tolist()
        labels = cards["label_en"].tolist()
        y = np.arange(len(cards))

        for col, strategy in enumerate(strategies):
            ax = axes[row, col]

            strategy_values = (
                card_results.loc[
                    (card_results["strategy"] == strategy)
                    & (card_results["card"].isin(card_ids)),
                    ["card", metric],
                ]
                .drop_duplicates("card")
                .set_index("card")
                .reindex(card_ids)[metric]
            )

            ax.barh(
                y,
                strategy_values,
                facecolor="none",
                edgecolor=category_color(category),
                linewidth=1.3,
            )

            if baseline is not None:
                ax.axvline(
                    baseline,
                    linestyle="--",
                    linewidth=0.8,
                )

            ax.set_xlim(xmin, xmax)
            ax.grid(axis="x", alpha=PLOT_STYLE["grid_alpha"])

            if row == 0:
                ax.set_title(strategy_label(strategy))

            if col == 0:
                ax.set_yticks(y)
                ax.set_yticklabels(labels)
                ax.set_ylabel(
                    category_label(category),
                    color=category_color(category),
                    fontweight="bold",
                )
            else:
                ax.set_yticks(y)
                ax.set_yticklabels([])

            if row == nrows - 1:
                ax.set_xlabel(
                    xlabel
                    or metric.replace("_", " ").title()
                )

    if title:
        fig.suptitle(title)

    fig.tight_layout()

    return fig, axes


def plot_category_strength_by_strategy(
    card_results,
    metric,
    *,
    baseline=None,
    ylabel=None,
    title=None,
    figsize=None,
):
    """
    One facet per strategy.

    Category means are outlined bars; individual card values are points.
    This shows both average category strength and within-category spread.
    """
    strategies = ordered_strategies(card_results)

    data = card_results.copy()
    data["_category"] = data["category"].apply(
        canonical_category
    )

    categories = list(dict.fromkeys(data["_category"]))

    fig, axes = plt.subplots(
        1,
        len(strategies),
        figsize=figsize or (
            3.1 * len(strategies),
            4.2,
        ),
        sharey=True,
        squeeze=False,
    )

    axes = axes[0]
    x = np.arange(len(categories))

    for ax, strategy in zip(axes, strategies):
        subset = data.loc[
            data["strategy"] == strategy
        ]

        means = (
            subset.groupby("_category")[metric]
            .mean()
            .reindex(categories)
        )

        ax.bar(
            x,
            means,
            facecolor="none",
            edgecolor=[
                category_color(category)
                for category in categories
            ],
            linewidth=1.4,
        )

        for position, category in zip(x, categories):
            values = subset.loc[
                subset["_category"] == category,
                metric,
            ].dropna()

            if values.empty:
                continue

            offsets = (
                np.array([0.0])
                if len(values) == 1
                else np.linspace(-0.16, 0.16, len(values))
            )

            ax.scatter(
                position + offsets,
                values,
                color=category_color(category),
                s=18,
                zorder=3,
            )

        if baseline is not None:
            ax.axhline(
                baseline,
                linestyle="--",
                linewidth=0.8,
            )

        ax.set_xticks(x)
        ax.set_xticklabels([
            category_label(category)
            for category in categories
        ])

        plt.setp(
            ax.get_xticklabels(),
            rotation=45,
            ha="right",
        )

        ax.set_title(strategy_label(strategy))
        ax.grid(axis="y", alpha=PLOT_STYLE["grid_alpha"])

    axes[0].set_ylabel(
        ylabel or metric.replace("_", " ").title()
    )

    if title:
        fig.suptitle(title)

    fig.tight_layout()

    return fig, axes
