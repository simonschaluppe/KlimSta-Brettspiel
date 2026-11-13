from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from card_colors import slot_colors, default_color


# ---------------------------------------------------------------------
# Central publication-style controls
# ---------------------------------------------------------------------
PLOT_STYLE = {
    # Figure dimensions
    "figsize": (7.2, 4.8),
    "wide_figsize": (10.0, 5.5),
    "tall_figsize": (7.2, 7.5),

    # Resolution
    "dpi": 140,
    "save_dpi": 300,

    # Typography
    "font_family": "Arial",
    "font_size": 10,
    "title_size": 12,
    "label_size": 10,
    "tick_size": 9,
    "legend_size": 9,

    # Layout
    "card_label_rotation": 45,
    "grid_alpha": 0.15,

    # Journal-style backgrounds
    "figure_background": "#eeeeee",
    "axes_background": "#ffffff",
}
# Optional. Add the actual game symbols here when available.
# Example:
# CATEGORY_ICONS["Wärmeerzeugung"] = "..."


def configure_plots():
    """Apply the common publication style to all matplotlib plots."""
    mpl.rcParams.update({
        "figure.figsize": PLOT_STYLE["figsize"],
        "figure.dpi": PLOT_STYLE["dpi"],

        "figure.facecolor": PLOT_STYLE["figure_background"],
        "axes.facecolor": PLOT_STYLE["axes_background"],
        "savefig.facecolor": PLOT_STYLE["figure_background"],

        "font.family": PLOT_STYLE["font_family"],
        "font.size": PLOT_STYLE["font_size"],

        "axes.titlesize": PLOT_STYLE["title_size"],
        "axes.labelsize": PLOT_STYLE["label_size"],

        "xtick.labelsize": PLOT_STYLE["tick_size"],
        "ytick.labelsize": PLOT_STYLE["tick_size"],

        "legend.fontsize": PLOT_STYLE["legend_size"],

        "axes.spines.top": False,
        "axes.spines.right": False,

        "axes.grid": False,
    })

CATEGORY_ALIASES = {
    "Abgabe": "Wärmeabgabe",
    "Wärmeabgabe": "Wärmeabgabe",
    "Dämmung": "Dämmung",
    "Dachnutzung": "Dachnutzung",
    "Fenster": "Fenster",
    "Flexibilität": "Flexibilität",
    "Effizienz": "Effizienz",
    "Lüftung": "Lüftung",
    "Wärmeerzeugung": "Wärmeerzeugung",
    "Zufriedenheit": "Nutzungsqualität",
    "Nutzungsqualität": "Nutzungsqualität",
}

CATEGORY_LABELS = {
    "Dämmung": "Insulation",
    "Fenster": "Windows",
    "Lüftung": "Ventilation",
    "Wärmeabgabe": "Heat delivery",
    "Wärmeerzeugung": "Heat generation",
    "Dachnutzung": "Roof use",
    "Flexibilität": "Flexibility",
    "Effizienz": "Efficiency",
    "Nutzungsqualität": "Amenities",
}
CATEGORY_ORDER = list(CATEGORY_LABELS)

CATEGORY_ICONS = {}


def canonical_category(category):
    """Normalize raw and legacy category names."""
    raw = str(category).lstrip("*").strip()
    return CATEGORY_ALIASES.get(raw, raw)


def category_color(category):
    """Return category color using the canonical category name."""
    return slot_colors.get(
        canonical_category(category),
        default_color,
    )


def category_label(category):
    """Return English category label, optionally with icon."""
    category = canonical_category(category)

    text = CATEGORY_LABELS.get(
        category,
        category,
    )

    icon = CATEGORY_ICONS.get(category, "")

    return f"{icon} {text}".strip()


def category_legend(categories):
    """Legend handles using the same colors as all category-aware card plots."""
    categories = list(reversed(dict.fromkeys(categories)))
    return [
        Patch(
            facecolor=category_color(category),
            label=category_label(category),
        )
        for category in categories
    ]


def finish_axis(
    ax,
    *,
    title=None,
    xlabel=None,
    ylabel=None,
    baseline=None,
    xgrid=False,
    ygrid=True,
):
    """Apply common labels, baseline and restrained grid styling."""
    if title:
        ax.set_title(title)

    if xlabel is not None:
        ax.set_xlabel(xlabel)

    if ylabel is not None:
        ax.set_ylabel(ylabel)

    if baseline is not None:
        ax.axhline(baseline, linestyle="--", linewidth=1)

    if xgrid:
        ax.grid(axis="x", alpha=PLOT_STYLE["grid_alpha"])

    if ygrid:
        ax.grid(axis="y", alpha=PLOT_STYLE["grid_alpha"])

    return ax


def rotate_card_labels(ax):
    """Use the same readable angle for card names on x axes."""
    plt.setp(
        ax.get_xticklabels(),
        rotation=PLOT_STYLE["card_label_rotation"],
        ha="right",
        rotation_mode="anchor",
    )

    return ax
def plot_card_bars(
    data,
    metric,
    *,
    ylabel,
    title,
    label_col="label_en",
    category_col="category",
    sort=True,
    group_by_category=True,
    baseline=None,
    show_legend=True,
    horizontal=True,
    figsize=None,
):
    """
    Publication-style card bar chart.

    group_by_category=True
        Keep cards grouped by category and sort cards within each category.
    """
    plot_data = data.dropna(subset=[metric]).copy()

    plot_data["_category"] = plot_data[category_col].apply(
        canonical_category
    )

    if group_by_category:
        plot_data["_category"] = pd.Categorical(
            plot_data["_category"],
            categories=CATEGORY_ORDER,
            ordered=True,
        )

        plot_data = plot_data.sort_values(
            ["_category", metric] if sort else ["_category"]
        )

    elif sort:
        plot_data = plot_data.sort_values(metric)

    colors = [
        category_color(category)
        for category in plot_data["_category"]
    ]

    if horizontal:
        fig, ax = plt.subplots(
            figsize=figsize or PLOT_STYLE["tall_figsize"]
        )

        y = np.arange(len(plot_data))

        ax.barh(
            y,
            plot_data[metric],
            color=colors,
        )

        ax.set_yticks(y)
        ax.set_yticklabels(plot_data[label_col])

        if baseline is not None:
            ax.axvline(
                baseline,
                linestyle="--",
                linewidth=1,
            )

        finish_axis(
            ax,
            title=title,
            xlabel=ylabel,
            ylabel="",
            ygrid=False,
            xgrid=True,
        )

    else:
        fig, ax = plt.subplots(
            figsize=figsize or PLOT_STYLE["wide_figsize"]
        )

        x = np.arange(len(plot_data))

        ax.bar(
            x,
            plot_data[metric],
            color=colors,
        )

        ax.set_xticks(x)
        ax.set_xticklabels(plot_data[label_col])
        rotate_card_labels(ax)

        finish_axis(
            ax,
            title=title,
            xlabel="",
            ylabel=ylabel,
            baseline=baseline,
        )

    if show_legend:
        ax.legend(
            handles=category_legend(plot_data["_category"]),
            title="Category",
            frameon=False,
        )

    fig.tight_layout()

    return fig, ax

def plot_card_scatter(
    data,
    x,
    y,
    *,
    xlabel,
    ylabel,
    title,
    label_col="label_en",
    category_col="category",
    labels=None,
    x_reference=None,
    y_reference=None,
    figsize=None,
):
    """
    Category-colored card scatter plot.

    `labels` can be a filtered DataFrame containing only the cards that
    should be annotated. Card annotations use the common 45° rotation.
    """
    plot_data = data.dropna(subset=[x, y]).copy()

    fig, ax = plt.subplots(
        figsize=figsize or PLOT_STYLE["tall_figsize"]
    )

    for category, group in plot_data.groupby(category_col, dropna=False):
        ax.scatter(
            group[x],
            group[y],
            color=category_color(category),
            label=category_label(category),
        )

    if x_reference is not None:
        ax.axvline(x_reference, linestyle="--", linewidth=1)

    if y_reference is not None:
        ax.axhline(y_reference, linestyle="--", linewidth=1)

    label_data = plot_data if labels is True else labels

    if label_data is not None:
        for _, row in label_data.iterrows():
            ax.annotate(
                row[label_col],
                (row[x], row[y]),
                fontsize=PLOT_STYLE["tick_size"],
                rotation=PLOT_STYLE["card_label_rotation"],
                ha="left",
                va="bottom",
            )

    finish_axis(
        ax,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
    )

    ax.legend(
        title="Category",
        frameon=False,
    )

    fig.tight_layout()

    return fig, ax


def plot_category_strength(
    card_data,
    metric,
    *,
    ylabel,
    title,
    category_col="category",
    label_col="label_en",
    baseline=None,
    label_cards=False,
):
    """
    Show category averages as bars with individual card values overlaid.

    This directly compares average category strength with within-category
    variation between technologies.
    """
    data = card_data.dropna(subset=[metric, category_col]).copy()

    category_means = (
        data.groupby(category_col)[metric]
        .mean()
        .sort_values()
    )

    categories = category_means.index.tolist()
    x = np.arange(len(categories))

    fig, ax = plt.subplots(
        figsize=PLOT_STYLE["wide_figsize"]
    )

    ax.bar(
        x,
        category_means.values,
        color=[category_color(category) for category in categories],
        alpha=0.70,
        label="Category mean",
    )

    for position, category in zip(x, categories):
        group = data.loc[data[category_col] == category].copy()

        if len(group) == 1:
            offsets = np.array([0.0])
        else:
            offsets = np.linspace(-0.18, 0.18, len(group))

        ax.scatter(
            position + offsets,
            group[metric],
            color=category_color(category),
            edgecolor="black",
            linewidth=0.5,
            zorder=3,
        )

        if label_cards:
            for offset, (_, row) in zip(offsets, group.iterrows()):
                ax.annotate(
                    row[label_col],
                    (position + offset, row[metric]),
                    fontsize=PLOT_STYLE["tick_size"] - 1,
                    rotation=PLOT_STYLE["card_label_rotation"],
                    ha="left",
                    va="bottom",
                )

    ax.set_xticks(x)
    ax.set_xticklabels([
        category_label(category)
        for category in categories
    ])

    rotate_card_labels(ax)

    finish_axis(
        ax,
        title=title,
        xlabel="",
        ylabel=ylabel,
        baseline=baseline,
    )

    fig.tight_layout()

    return fig, ax


def plot_rule_metric(
    card_results,
    card,
    metric,
    *,
    ylabel,
    title=None,
    reference=None,
    ax=None,
    show_legend=True,
):
    data = card_results.loc[
        card_results["card"] == card
    ].copy()

    table = data.pivot(
        index="pass_probability",
        columns="access_rule",
        values=metric,
    )

    own_figure = ax is None

    if own_figure:
        fig, ax = plt.subplots(
            figsize=PLOT_STYLE["figsize"]
        )
    else:
        fig = ax.figure

    for column in table.columns:
        ax.plot(
            table.index,
            table[column],
            marker="o",
            label=column,
        )

    if reference is not None:
        ax.axhline(
            reference,
            linestyle="--",
            linewidth=1,
        )

    finish_axis(
        ax,
        title=title or metric.replace("_", " ").title(),
        xlabel="Pass probability",
        ylabel=ylabel,
    )

    if show_legend:
        ax.legend(
            title="Access rule",
            frameon=False,
        )

    if own_figure:
        fig.tight_layout()

    return fig, ax
def plot_vp_with_without_facets(
    games,
    card_data,
    *,
    bins=30,
    figsize=None,
):
    """
    Compare final-VP distributions with/without every card.

    Rows = card categories
    Columns = cards within each category

    All facets share x/y axes and use the same VP bins.
    """

    cards = (
        card_data[
            ["card", "label_en", "category"]
        ]
        .drop_duplicates("card")
        .copy()
    )

    cards["_category"] = cards["category"].apply(
        canonical_category
    )

    # Use central category order.
    categories = [
        category
        for category in CATEGORY_ORDER
        if category in cards["_category"].unique()
    ]

    cards_by_category = {
        category: (
            cards.loc[cards["_category"] == category]
            .sort_values("label_en")
        )
        for category in categories
    }

    nrows = len(categories)
    ncols = max(
        len(group)
        for group in cards_by_category.values()
    )

    # Same bins for every facet.
    vp_bins = np.linspace(
        games["vp"].min(),
        games["vp"].max(),
        bins + 1,
    )

    if figsize is None:
        figsize = (
            max(10, 2.4 * ncols),
            max(8, 1.8 * nrows),
        )

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=figsize,
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    for row, category in enumerate(categories):

        category_cards = cards_by_category[category]
        color = category_color(category)

        for col in range(ncols):

            ax = axes[row, col]

            if col >= len(category_cards):
                ax.set_visible(False)
                continue

            card = category_cards.iloc[col]
            card_id = card["card"]

            has_card = games["played_cards"].apply(
                lambda played: card_id in played
            )

            # Without card
            ax.hist(
                games.loc[~has_card, "vp"],
                bins=vp_bins,
                density=True,
                histtype="step",
                linewidth=1.0,
                linestyle="--",
                color="#888888",
            )

            # With card
            ax.hist(
                games.loc[has_card, "vp"],
                bins=vp_bins,
                density=True,
                histtype="step",
                linewidth=1.6,
                color=color,
            )

            ax.set_title(
                card["label_en"],
                fontsize=PLOT_STYLE["tick_size"],
            )

            ax.grid(
                axis="y",
                alpha=PLOT_STYLE["grid_alpha"],
            )

            # Category name at left of each row.
            if col == 0:
                ax.set_ylabel(
                    category_label(category),
                    color=color,
                    fontweight="bold",
                )

            # Only bottom occupied facet gets x labels.
            if row == nrows - 1:
                ax.set_xlabel("Final VP")

    # Common legend
    legend_handles = [
        plt.Line2D(
            [0], [0],
            color="#555555",
            linewidth=1.6,
            label="With card",
        ),
        plt.Line2D(
            [0], [0],
            color="#888888",
            linewidth=1.0,
            linestyle="--",
            label="Without card",
        ),
    ]

    fig.legend(
        handles=legend_handles,
        loc="upper center",
        ncol=2,
        frameon=False,
    )

    fig.suptitle(
        "Final VP distributions with and without individual technologies",
        y=1.01,
    )

    fig.supxlabel("Final VP")
    fig.supylabel("Density")

    fig.tight_layout()

    return fig, axes

def plot_card_metric_heatmap(
    card_results,
    metric="vp_lift",
    *,
    title=None,
    center=None,
    cmap="coolwarm",
    figsize=None,
    vmin=None,
    vmax=None,
):
    data = card_results.copy()

    data["condition"] = (
        data["access_rule"]
        + "\np="
        + data["pass_probability"].astype(str)
    )

    # card is the unique technology identifier
    table = data.pivot(
        index="card",
        columns="condition",
        values=metric,
    )

    # Human-readable labels for plotting
    card_info = (
        data[
            ["card", "label_en", "category"]
        ]
        .drop_duplicates("card")
        .set_index("card")
    )

    # Sort by category, then card name
    order = (
        card_info
        .assign(
            _category=lambda x: x["category"].apply(canonical_category)
        )
        .sort_values(["_category", "label_en"])
        .index
    )

    table = table.loc[order]
    card_info = card_info.loc[order]

    fig, ax = plt.subplots(
        figsize=figsize or (12, 9)
    )

    if center is not None:

        if vmin is None or vmax is None:
            limit = np.nanmax(
                np.abs(table.values - center)
            )

            if vmin is None:
                vmin = center - limit

            if vmax is None:
                vmax = center + limit

        image = ax.imshow(
            table.values,
            aspect="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )

    else:
        image = ax.imshow(
            table.values,
            aspect="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )

    ax.set_xticks(range(len(table.columns)))
    ax.set_xticklabels(
        table.columns,
        rotation=45,
        ha="right",
    )

    ax.set_yticks(range(len(table.index)))
    ax.set_yticklabels(
        card_info["label_en"]
    )

    ax.set_xlabel("")
    ax.set_ylabel("")

    if title:
        ax.set_title(title)

    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(
        metric.replace("_", " ").title()
    )

    fig.tight_layout()

    return fig, ax

def save_figure(fig, figure_dir, filename):
    """Save a figure using the central publication DPI."""
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    path = figure_dir / filename

    fig.savefig(
        path,
        dpi=PLOT_STYLE["save_dpi"],
        bbox_inches="tight",
    )

    return path
