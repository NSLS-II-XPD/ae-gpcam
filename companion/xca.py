import tensorflow as tf
from pathlib import Path
import numpy as np
import json


class XCACompanion:
    def __init__(self, model_name='background_lite'):

        self.model_name = model_name
        model_path = Path('./saved_models/') / model_name
        self.model = tf.keras.models.load_model(str(model_path))
        self.phasemap = {0: 'MgCu2', 1: 'Mg', 2: 'Ti', 3: 'Mg2Cu'}

    def _preprocessing(self, doc):
        """Takes document and converts it to relevant Q range for Neural net"""
        if self.model_name == 'background_lite':
            data = doc["data"]
            Is = np.array(data["mean"])
            Qs = np.array(data["q"])
            q_range = (2, 4)
            idx_min = np.where(Qs[0, :] < q_range[0])[0][-1] if len(np.where(Qs[0, :] < q_range[0])[0]) else 0
            idx_max = np.where(Qs[0, :] > q_range[1])[0][0] if len(np.where(Qs[0, :] > q_range[1])[0]) else Is.shape[1]
            Is = Is[:, idx_min:idx_max]
            I_norm = (Is - np.min(Is, axis=1, keepdims=True)) / \
                     (np.max(Is, axis=1, keepdims=True) - np.min(Is, axis=1, keepdims=True))
            # Dimensions are imporant and TF is picky.
            I_norm = np.reshape(I_norm, (-1, 576, 1))
            return I_norm

        else:
            raise ValueError(f"{self.model_name} is not a known model type for preprocessing")

    def predict(self, doc):
        # Everything should be conceptualized as batch processing of (576, 1) arrays, even if it is a batch of 1
        X = self._preprocessing(doc)
        X = tf.convert_to_tensor(X, dtype=tf.float32)
        y_preds = self.model(X, training=False)
        return y_preds

    @staticmethod
    def entropy(y_preds):
        H = np.sum(-y_preds * np.log2(y_preds), axis=-1)
        return H

    def ask(self):
        pass

    def tell(self):
        pass


if __name__ == "__main__":
    # THIS IS A BAD HACK FOR MAC TESTING #
    import os
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    # THIS IS A BAD HACK FOR MAC TESTING #

    import databroker

    xca = XCACompanion()

    # Creating a pretend document via dictionary
    cat = databroker._drivers.msgpack.BlueskyMsgpackCatalog(
        str(Path('~/Documents/Project-Adaptive/KarenChenWiegart/kyc_day1/*').expanduser()))
    for name in cat:
        print(name)
        ds = cat[name].primary.read()
    doc = {'data': {'mean': ds['mean'], 'q': ds['q']}}

    y_preds = xca.predict(doc)
    print(y_preds)
    print(xca.entropy(y_preds))
