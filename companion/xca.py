import tensorflow as tf
from pathlib import Path
import numpy as np
from event_model import RunRouter
from event_model import DocumentRouter
from event_model import unpack_event_page
from bluesky.run_engine import Dispatcher, DocumentNames
import matplotlib.pyplot as plt
import json
from bluesky.utils import install_qt_kicker
from itertools import cycle
from data_access.acces_grid import single_strip_set_transform_factory, load_from_json
from dataclasses import dataclass, asdict


@dataclass
class Proposal:
    phase_of_interest: str
    x: float
    y: float
    sci_coords: list
    probabilities: list


class XCACompanion:
    def __init__(
        self,
        model_name="bkg_ideal",
        q_range=(2, 4),
        transform_path="../data_access/layout.json",
        ignore_phases=("Mg",),
    ):

        self.model_name = model_name
        model_path = Path("./saved_models/") / model_name
        self.model = tf.keras.models.load_model(str(model_path))
        self.phasemap = {0: "MgCu2", 1: "Mg", 2: "Ti", 3: "Mg2Cu"}
        self.phase_idx = [
            key for key in self.phasemap if self.phasemap[key] not in ignore_phases
        ]
        self.strip_infos = load_from_json(transform_path)
        self.strip_transforms = single_strip_set_transform_factory(self.strip_infos)
        self.strip_ys = cycle([strip.reference_y for strip in self.strip_infos])
        self.q_range = q_range
        self.independent = None
        self.dependent = None
        self.cache = set()  # Hashable cache of proposals
        self.proposals = list()  # More data rich list of proposals

    def _preprocessing(self, IoQ):
        """Takes array [[Q],[I]] and converts it to relevant Q range for Neural net"""
        if self.model_name in (
            "background_lite",
            "background",
            "bkg_limit_texture",
            "bkg_ideal",
        ):
            # Qs = np.array(data["q"])
            Qs = IoQ[:, :, 0]
            Is = IoQ[:, :, 1]
            q_range = self.q_range
            idx_min = (
                np.where(Qs[0, :] < q_range[0])[0][-1]
                if len(np.where(Qs[0, :] < q_range[0])[0])
                else 0
            )
            idx_max = (
                np.where(Qs[0, :] > q_range[1])[0][0]
                if len(np.where(Qs[0, :] > q_range[1])[0])
                else Is.shape[1]
            )
            Is = Is[:, idx_min:idx_max]
            I_norm = (Is - np.min(Is, axis=1, keepdims=True)) / (
                np.max(Is, axis=1, keepdims=True) - np.min(Is, axis=1, keepdims=True)
            )
            # Dimensions are imporant and TF is picky.
            I_norm = np.reshape(I_norm, (-1, 576, 1))
            return I_norm

        else:
            raise ValueError(
                f"{self.model_name} is not a known model type for preprocessing"
            )

    def predict(self, IoQ):
        # Everything should be conceptualized as batch processing of (576, 1) arrays, even if it is a batch of 1
        X = self._preprocessing(IoQ)
        X = tf.convert_to_tensor(X, dtype=tf.float32)
        y_preds = self.model(X, training=False)
        return [y_preds[i, :] for i in range(y_preds.shape[0])]

    @staticmethod
    def entropy(y_preds):
        # Maximum entropy is Sum((1/n_classes)*log2(1/n_classes)) = 2.0 for 4 classes.
        H = np.sum(-y_preds * np.log2(y_preds + 1e-16), axis=-1)
        return H

    def ask(self, n, tell_pending=True):
        """
        Cycle all maximum posterior probability of each phases of interest in a given strip, then repeat for all strips.
        Then repeat for the full cycle until all n are satisfied.
        Parameters
        ----------
        n
        tell_pending

        Returns
        -------

        """
        n = min(n, len(self.independent))  # Avoid unecessary looping.
        proposals = []
        for (
            current_y
        ) in self.strip_ys:  # Strip ys is a cycle, so will continue indefinitely
            # Get our interesting indexes sorted according to phase where the strip is current
            for phase in self.phase_idx:
                idxs = np.argsort(self.dependent[:, phase])[::-1]
                jdxs = [i for i in idxs if np.abs(self.independent[i, 1] - current_y) < 4.5 / 2]
                for j in jdxs:
                    proposal = self.independent[j, :]
                    if tuple(proposal) in self.cache:
                        continue
                    else:
                        self.cache.add(tuple(proposal))
                        proposals.append(self.strip_transforms.inverse(*proposal))
                        self.proposals.append(
                            Proposal(
                                phase_of_interest=self.phasemap[phase],
                                x=proposal[0],
                                y=proposal[1],
                                sci_coords=proposals[-1],
                                probabilities=self.dependent[j, :],
                            )
                        )
                        if len(proposals) >= n:
                            return proposals
                        else:
                            break

    def tell(self, x, y):
        """
        Tell XCA about something new
        Parameters
        ----------
        x: These are the interesting parameters
        y: This should be the Q/I(Q) shape (n, 2). [[Q],[I]]

        Returns
        -------

        """
        ys = np.reshape(y, (1, -1, 2))
        xs = np.reshape(x, (1, -1))
        self.tell_many(xs, ys)

    def tell_many(self, xs, ys):
        """
        Tell XCA about many new things
        Parameters
        ----------
        xs: These are the interesting parameters, they get converted to an 2d space via a transform
        ys: list, arr
            This should be a list length m of the Q/I(Q) shape (n, 2)

        Returns
        -------

        """
        keep_i = []
        new_independents = []
        for i in range(xs.shape[0]):
            try:
                new_independents.append(self.strip_transforms.forward(*xs[i, :]))
            except ValueError:
                continue
            keep_i.append(i)
        X = np.array(ys)[keep_i, :]
        y_preds = np.array(self.predict(X))
        if self.independent is None:
            self.independent = np.array(new_independents)
            self.dependent = y_preds
        else:
            self.independent = np.vstack([self.independent, new_independents])
            self.dependent = np.vstack([self.dependent, y_preds])


def record_output_probabilities(xca, out_path):
    """Helper function to record XCA probabilities over initial scan to file"""
    from pandas import DataFrame

    data_dict = {}

    data_dict["Position 0"] = xca.independent[:, 0]
    data_dict["Position 1"] = xca.independent[:, 1]
    for idx in xca.phasemap:
        data_dict[f"Probability of {xca.phasemap[idx]}"] = xca.dependent[:, idx]

    df = DataFrame.from_dict(data_dict)
    df.to_csv(out_path)
    return df


def record_detailed_proposals(xca, out_path):
    from pandas import DataFrame

    dicts = [asdict(p) for p in xca.proposals]
    df = DataFrame(dicts)

    df[["Ti_frac", "temperature", "annealing_time", "thickness"]] = DataFrame(
        df["sci_coords"].tolist(), index=df.index
    )
    df[[f"Prby {xca.phasemap[i]}" for i in range(4)]] = DataFrame(
        df["probabilities"].tolist(), index=df.index
    )
    del df["probabilities"]
    del df["sci_coords"]
    df.to_csv(out_path)
    return df


if __name__ == "__main__":
    from data_access.acces_grid import pre_process

    # THIS IS A BAD HACK FOR MAC TESTING #
    import os

    os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
    # THIS IS A BAD HACK FOR MAC TESTING #

    import databroker._drivers.msgpack

    xca = XCACompanion()

    # Creating a pretend document via dictionary
    # Do the work of extract_event_page()
    cat = databroker._drivers.msgpack.BlueskyMsgpackCatalog(
        "/mnt/data/bnl/2020-12_ae/kyc_day1/*.msgpack"
    )

    for name in ["73ac6ea4-a528-4fb7-ae2f-eb44ed8d684d"]:
        print(name)
        ds = cat[name].primary.read()

    science_pos, x, y, Q, I, roi = pre_process(ds, xca.strip_transforms)
    measurement = np.stack([np.array(Q), np.array(I)], axis=-1)
    independent = np.array(science_pos)  # 4 space

    xca.tell_many(independent, measurement)

    cat2 = databroker._drivers.msgpack.BlueskyMsgpackCatalog(
        "/mnt/data/bnl/2020-12_ae/day2_reduced/*.msgpack"
    )

    I_cache = []
    Q_cache = []
    independent_cache = []
    for h in (cat2[uid] for uid in cat2):
        Q_cache.append(cat2[-1].primary().read()["q"].mean(axis=0).values)
        I_cache.append(cat2[-1].primary().read()["mean"].mean(axis=0).values)
        d = h.metadata["start"]["adaptive_step"]["snapped"]
        independent_cache.append(
            [
                d[k]
                for k in [
                    "ctrl_Ti",
                    "ctrl_temp",
                    "ctrl_annealing_time",
                    "ctrl_thickness",
                ]
            ]
        )

    measurement = np.stack([np.array(Q_cache), np.array(I_cache)], axis=-1)
    independent = np.array(independent_cache)  # 4 space
    xca.tell_many(independent, measurement)

    df_prby = record_output_probabilities(xca, "output_probabilities.csv")
    proposals1 = xca.ask(27)
    proposals2 = xca.ask(27)
    df_prop = record_detailed_proposals(xca, "output_proposals.csv")
    # print(proposals)
