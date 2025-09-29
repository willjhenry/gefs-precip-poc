import tensorflow as tf

from hydro.models.loss_functions import crps_loss


def gamma_nn_model(X_train, hidden_units=(64, 32, 32)):
    # Define a NN with an input layer, two hidden layers, and an output layer.
    # The output layer has two neurons, using softplus to ensure the output is positive.
    # pyrefly: ignore
    inputs = tf.keras.Input(shape=(X_train.shape[1],))
    # pyrefly: ignore
    x = tf.keras.layers.Dense(hidden_units[0], activation="relu")(inputs)
    for units in hidden_units[1:]:
        # pyrefly: ignore
        x = tf.keras.layers.Dense(units, activation="relu")(x)
    # pyrefly: ignore
    outputs = tf.keras.layers.Dense(2, activation="softplus")(
        x
    )  # Positive shape/scale
    # pyrefly: ignore
    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer="adam", loss=crps_loss)  # Custom loss
    return model
