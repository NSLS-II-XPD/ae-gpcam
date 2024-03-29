"Non-negative matrix factorization of full datasets"
from sklearn.decomposition import NMF
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl


def decomposition(Q, I, n_components=3, q_range=None, max_iter=10000, bkg_removal=None, normalize=False):
    """
    Decompose and label a set of I(Q) data with optional focus bounds

    Parameters
    ----------
    Q : array
        Ordinate Q for I(Q). Assumed to be rank 2, shape (m_patterns, n_data)
    I : array
        The intensity values for each Q, assumed to be the same shape as Q. (m_patterns, n_data)
    n_components: int
        Number of components for NMF
    q_range : tuple, list
        (Min, Max) Q values for consideration in NMF. This enables a focused region for decomposition.

    Returns
    -------
    sub_Q : array
        Subsampled ordinate used for NMF
    sub_I : array
        Subsampled I used for NMF
    alphas : array
        Resultant weights from NMF

    """

    nmf = NMF(n_components=n_components, max_iter=max_iter)

    if q_range is None:
        idx_min = 0
        idx_max = I.shape[1]
    else:
        idx_min = np.where(Q[0, :] < q_range[0])[0][-1] if len(np.where(Q[0, :] < q_range[0])[0]) else 0
        idx_max = np.where(Q[0, :] > q_range[1])[0][0] if len(np.where(Q[0, :] > q_range[1])[0]) else I.shape[1]

    sub_I = I[:, idx_min:idx_max]
    sub_Q = Q[:, idx_min:idx_max]

    if bkg_removal:
        import peakutils
        bases = []
        for i in range(sub_I.shape[0]):
            bases.append(peakutils.baseline(sub_I[i, :], deg=bkg_removal))
        bases = np.stack(bases)
        sub_I = sub_I - bases
    if normalize:
        sub_I = (sub_I - np.min(I, axis=1, keepdims=True)) / (
                np.max(sub_I, axis=1, keepdims=True) - np.min(sub_I, axis=1, keepdims=True))

    # Numerical stability of non-negativity
    if np.min(sub_I) < 0:
        sub_I = sub_I - np.min(sub_I, axis=1, keepdims=True)

    alphas = nmf.fit_transform(sub_I)

    return sub_Q, sub_I, alphas


def waterfall_plot(ax, xs, ys, alt_ordinate=None, sampling=1, offset=1.0, cmap='viridis', **kwargs):
    indicies = range(0, xs.shape[0])[::sampling]

    cmap = mpl.cm.get_cmap(cmap)
    norm = mpl.colors.Normalize(vmin=0, vmax=xs.shape[0]//sampling)

    if alt_ordinate is not None:
        idxs, labels = list(zip(*sorted(zip(range(ys.shape[0]), alt_ordinate), key=lambda x: x[1])))
    else:
        idxs = list(range(ys.shape[0]))
        labels = list(range(ys.shape[0]))

    for plt_i, idx in enumerate(indicies):
        y = ys[idx, :]
        y = y + plt_i * offset
        x = xs[idx, :]
        ax.plot(x, y, color=cmap(norm(plt_i)))

    ax.set_ylim((0, len(indicies)))
    ax.set_yticks([0, len(indicies) // 2, len(indicies)])
    ax.set_yticklabels([labels[0], labels[len(labels)//2], labels[-1]])


def waterfall(ax, xs, ys, alphas, color='k', sampling=1, offset=0.2, **kwargs):
    indicies = range(0, xs.shape[0])[::sampling]
    for plt_i, idx in enumerate(indicies):
        y = ys[idx, :] + plt_i * offset
        x = xs[idx, :]
        ax.plot(x, y, color=color, alpha=alphas[idx], **kwargs)
    return ax


def example_plot(sub_Q, sub_I, alphas, axes=None, sax=None, cmap='tab10', alt_ordinate=None, offset=1.,
                 summary_fig=False):
    """
    Example plotting of NMF results. Not necessarily for Bluesky deployment

    Parameters
    ----------
    sub_Q: array
        Q to plot in I(Q)
    sub_I: array
        I to plot in I(Q)
    alphas: array
        transparencies of multiple repeated plots of I(Q)
    axes: optional existing axes for waterfalls
    sax: optional axes for summary figure
    cmap: mpl colormap
    alt_ordinate: array
        Array len sub_I.shape[0], corresponding to an alternative labeled dimension for which to order the stacked plots
    summary_fig: bool
        Whether to include separate figure o alphas over the ordinate

    Returns
    -------
    fig, axes

    """

    n_components = alphas.shape[1]
    cmap = mpl.cm.get_cmap(cmap)
    norm = mpl.colors.Normalize(vmin=0, vmax=n_components)

    # Create alternative ordinate for the waterfall/stacking
    if alt_ordinate is not None:
        idxs, labels = list(zip(*sorted(zip(range(sub_I.shape[0]), alt_ordinate), key=lambda x: x[1])))
    else:
        idxs = list(range(sub_I.shape[0]))
        labels = list(range(sub_I.shape[0]))
    xs = sub_Q[idxs, :]
    ys = sub_I[idxs, :]
    alphas = alphas[idxs, :]

    # Order by proxy center of mass of class in plot regime. Makes the plots feel like a progression not random.
    alpha_ord = np.argsort(np.matmul(np.arange(alphas.shape[0]), alphas))

    if axes is None:
        fig, axes = plt.subplots(int(np.ceil(np.sqrt(n_components))), int(np.ceil(np.sqrt(n_components))))
        axes = axes.reshape(-1)
    else:
        axes = np.ravel(axes)
    for i, ax in enumerate(axes):
        if i < n_components:
            i_a = alpha_ord[i]
            color = cmap(norm(i))
            alpha = (alphas[:, i_a] - np.min(alphas[:, i_a])) / (np.max(alphas[:, i_a]) - np.min(alphas[:, i_a]))
            ax = waterfall(ax, xs, ys, alpha, color=color, offset=offset)
        else:
            ax.set_visible = False

    if summary_fig:
        if sax is None:
            sfig, sax = plt.subplots(figsize=(6, 6))

        sx = np.arange(0, alphas.shape[0])
        for i in range(alphas.shape[1]):
            sax.plot(sx, alphas[:, alpha_ord[i]], color=cmap(norm(i)), label=f"Component {i + 1}")

        return axes, sax

    return axes[0].figure, axes
