import tensorflow as tf

from hydro.models.loss_functions import crps_loss


def gamma_nn_model(
    X_train, hidden_units=(8, 2), dropout_rate=0.2, l1=0.0, l2=1e-4
):
    # Define a NN with an input layer, two hidden layers, and an output layer.
    # The output layer has two neurons, using softplus to ensure the output is positive.
    if l1 and l2:
        reg = tf.keras.regularizers.l1_l2(l1, l2)
    elif l1:
        reg = tf.keras.regularizers.l1(l1)
    elif l2:
        reg = tf.keras.regularizers.l2(l2)
    else:
        reg = None
    # pyrefly: ignore
    inputs = tf.keras.Input(shape=(X_train.shape[1],))
    x = inputs
    for units in hidden_units:
        # pyrefly: ignore
        x = tf.keras.layers.Dense(
            units, activation="relu", kernel_regularizer=reg
        )(x)
        if dropout_rate:
            # pyrefly: ignore
            x = tf.keras.layers.Dropout(dropout_rate)(x)
    # pyrefly: ignore
    outputs = tf.keras.layers.Dense(2, activation="softplus")(x)
    # pyrefly: ignore
    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer="adam", loss=crps_loss)  # Custom loss
    return model
