# coding: utf-8
import sys
import time

from utils import *
from rnnmath import *
from sys import stdout
from model import Model
from rnn import RNN
from gru import GRU


class Runner(object):
    '''
    This class implements the training loop for a Model (either an RNN or a GRU).
    Parameters such as hidden_size can be accessed via the model.

    You should implement code in the following functions:
    	compute_loss 		->	compute the (cross entropy) loss between the desired output and predicted output for a given input sequence
    	compute_loss_np     ->  compute the loss between the desired output and predicted output for a given input sequence for the number prediction task
    	compute_mean_loss	->	compute the average loss over all sequences in a corpus
    	compute_acc_np      ->  compute the

    Do NOT modify any other methods!
    Do NOT change any method signatures!
    '''

    def __init__(self, model: Model):
        self.model = model

    def compute_loss(self, x, d):
        '''
        compute the loss between predictions y for x, and desired output d.

        first predicts the output for x using the Model, then computes the loss w.r.t. d

        x		list of words, as indices, e.g.: [0, 4, 2]
        d		list of words, as indices, e.g.: [4, 2, 3]

        return loss		the combined loss for all words
        '''
        loss = 0.
        y, _ = self.model.predict(x)
        for t in range(len(x)):
            y_true = make_onehot(d[t], self.model.vocab_size)
            log_y_pred = np.log(y[t])
            loss -= np.dot(y_true, log_y_pred)
        return loss

    def compute_loss_np(self, x, d):
        '''
        compute the loss between predictions y for x, and desired output d.

        first predicts the output for x using the RNN, then computes the loss w.r.t. d

        x		list of words, as indices, e.g.: [0, 4, 2]
        d		a word, as indices, e.g.: [0]

        return loss		we only take the prediction from the last time step
        '''
        loss = 0.
        y, _ = self.model.predict(x)
        t = len(x)-1
        log_y_pred = np.log(y[t])
        one_hot_dt = make_onehot(d[0], self.model.vocab_size)
        loss -= np.dot(one_hot_dt, log_y_pred)
        return loss

    def compute_acc_np(self, x, d):
        '''
        compute the accuracy prediction, y[t] compared to the desired output d.
        first predicts the output for x using the RNN, then computes the loss w.r.t. d

        x		list of words, as indices, e.g.: [0, 4, 2]
        d		a word class (plural/singular), as index, e.g.: [0] or [1]

        return 1 if argmax(y[t]) == d[0], 0 otherwise
        '''
        y, _ = self.model.predict(x)
        t = len(x)-1
        return int(np.argmax(y[t]) == d[0])

    def compute_mean_loss(self, X, D):
        '''
        compute the mean loss between predictions for corpus X and desired outputs in corpus D.

        X		corpus of sentences x1, x2, x3, [...], each a list of words as indices.
        D		corpus of desired outputs d1, d2, d3 [...], each a list of words as indices.

        return mean_loss		average loss over all words in D
        '''
        mean_loss = 0.
        word_count = 0
        for x, d in zip(X, D):
            mean_loss += self.compute_loss(x, d)
            word_count += len(x)
        return mean_loss / word_count

    def train(self, X, D, X_dev, D_dev, epochs=10, learning_rate=0.5, anneal=5, back_steps=0, batch_size=100,
              min_change=0.0001, log=True):
        '''
        train the model on some training set X, D while optimizing the loss on a dev set X_dev, D_dev

        DO NOT CHANGE THIS

        training stops after the first of the following is true:
            * number of epochs reached
            * minimum change observed for more than 2 consecutive epochs

        X				a list of input vectors, e.g., 		[[0, 4, 2], [1, 3, 0]]
        D				a list of desired outputs, e.g., 	[[4, 2, 3], [3, 0, 3]]
        X_dev			a list of input vectors, e.g., 		[[0, 4, 2], [1, 3, 0]]
        D_dev			a list of desired outputs, e.g., 	[[4, 2, 3], [3, 0, 3]]
        epochs			maximum number of epochs (iterations) over the training set. default 10
        learning_rate	initial learning rate for training. default 0.5
        anneal			positive integer. if > 0, lowers the learning rate in a harmonically after each epoch.
                        higher annealing rate means less change per epoch.
                        anneal=0 will not change the learning rate over time.
                        default 5
        back_steps		positive integer. number of timesteps for BPTT. if back_steps < 2, standard BP will be used. default 0
        batch_size		number of training instances to use before updating the RNN's weight matrices.
                        if set to 1, weights will be updated after each instance. if set to len(X), weights are only updated after each epoch.
                        default 100
        min_change		minimum change in loss between 2 epochs. if the change in loss is smaller than min_change, training stops regardless of
                        number of epochs left.
                        default 0.0001
        log				whether or not to print out log messages. (default log=True)
        '''
        if log:
            stdout.write(
                "\nTraining model for {0} epochs\ntraining set: {1} sentences (batch size {2})".format(epochs, len(X),
                                                                                                       batch_size))
            stdout.write("\nOptimizing loss on {0} sentences".format(len(X_dev)))
            stdout.write("\nVocab size: {0}\nHidden units: {1}".format(self.model.vocab_size, self.model.hidden_dims))
            stdout.write("\nSteps for back propagation: {0}".format(back_steps))
            stdout.write("\nInitial learning rate set to {0}, annealing set to {1}".format(learning_rate, anneal))
            stdout.write("\n\ncalculating initial mean loss on dev set")
            stdout.flush()

        t_start = time.time()
        loss_function = self.compute_loss

        loss_sum = sum([len(d) for d in D_dev])
        initial_loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / loss_sum

        if log or not log:
            stdout.write(": {0}\n".format(initial_loss))
            stdout.flush()

        prev_loss = initial_loss
        loss_watch_count = -1
        min_change_count = -1

        a0 = learning_rate

        best_loss = initial_loss
        self.model.save_params()
        best_epoch = 0

        for epoch in range(epochs):
            if anneal > 0:
                learning_rate = a0 / ((epoch + 0.0 + anneal) / anneal)
            else:
                learning_rate = a0

            if log:
                stdout.write("\nepoch %d, learning rate %.04f" % (epoch + 1, learning_rate))
                stdout.flush()

            t0 = time.time()
            count = 0

            # use random sequence of instances in the training set (tries to avoid local maxima when training on batches)
            permutation = np.random.permutation(range(len(X)))
            if log:
                stdout.write("\tinstance 1")
            for i in range(len(X)):
                c = i + 1
                if log:
                    stdout.write("\b" * len(str(i)))
                    stdout.write("{0}".format(c))
                    stdout.flush()
                p = permutation[i]
                x_p = X[p]
                d_p = D[p]

                y_p, s_p = self.model.predict(x_p)
                if back_steps == 0:
                    self.model.acc_deltas(x_p, d_p, y_p, s_p)
                else:
                    self.model.acc_deltas_bptt(x_p, d_p, y_p, s_p, back_steps)

                if i % batch_size == 0:
                    self.model.scale_gradients_for_batch(batch_size)
                    self.model.apply_deltas(learning_rate)

            if len(X) % batch_size > 0:
                mod = len(X) % batch_size
                self.model.scale_gradients_for_batch(mod)
                self.model.apply_deltas(learning_rate)

            loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / loss_sum

            if log:
                stdout.write("\tepoch done in %.02f seconds" % (time.time() - t0))
                stdout.write("\tnew loss: {0}".format(loss))
                stdout.flush()

            if loss < best_loss:
                best_loss = loss
                self.model.save_params()
                best_epoch = epoch

            # make sure we change the RNN enough
            if abs(prev_loss - loss) < min_change:
                min_change_count += 1
            else:
                min_change_count = 0
            if min_change_count > 2:
                print("\n\ntraining finished after {0} epochs due to minimal change in loss".format(epoch + 1))
                break

            prev_loss = loss

        t = time.time() - t_start

        if min_change_count <= 2:
            print("\n\ntraining finished after reaching maximum of {0} epochs".format(epochs))
        print("best observed loss was {0}, at epoch {1}".format(best_loss, (best_epoch + 1)))

        print("setting parameters to matrices from best epoch")
        self.model.set_best_params()

        return best_loss

    def train_np(self, X, D, X_dev, D_dev, epochs=10, learning_rate=0.5, anneal=5, back_steps=0, batch_size=100,
                 min_change=0.0001, log=True):
        '''
        train the model on some training set X, D while optimizing the loss on a dev set X_dev, D_dev

        DO NOT CHANGE THIS

        training stops after the first of the following is true:
            * number of epochs reached
            * minimum change observed for more than 2 consecutive epochs

        X				a list of input vectors, e.g., 		[[5, 4, 2], [7, 3, 8]]
        D				a list of desired outputs, e.g., 	[[0], [1]]
        X_dev			a list of input vectors, e.g., 		[[5, 4, 2], [7, 3, 8]]
        D_dev			a list of desired outputs, e.g., 	[[0], [1]]
        epochs			maximum number of epochs (iterations) over the training set. default 10
        learning_rate	initial learning rate for training. default 0.5
        anneal			positive integer. if > 0, lowers the learning rate in a harmonically after each epoch.
                        higher annealing rate means less change per epoch.
                        anneal=0 will not change the learning rate over time.
                        default 5
        back_steps		positive integer. number of timesteps for BPTT. if back_steps < 2, standard BP will be used. default 0
        batch_size		number of training instances to use before updating the RNN's weight matrices.
                        if set to 1, weights will be updated after each instance. if set to len(X), weights are only updated after each epoch.
                        default 100
        min_change		minimum change in loss between 2 epochs. if the change in loss is smaller than min_change, training stops regardless of
                        number of epochs left.
                        default 0.0001
        log				whether or not to print out log messages. (default log=True)
        '''
        if log:
            stdout.write(
                "\nTraining model for {0} epochs\ntraining set: {1} sentences (batch size {2})".format(epochs, len(X),
                                                                                                       batch_size))
            stdout.write("\nOptimizing loss on {0} sentences".format(len(X_dev)))
            stdout.write("\nVocab size: {0}\nHidden units: {1}".format(self.model.vocab_size, self.model.hidden_dims))
            stdout.write("\nSteps for back propagation: {0}".format(back_steps))
            stdout.write("\nInitial learning rate set to {0}, annealing set to {1}".format(learning_rate, anneal))
            stdout.flush()

        t_start = time.time()
        loss_function = self.compute_loss_np

        loss_sum = len(D_dev)
        initial_loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / loss_sum
        initial_acc = sum([self.compute_acc_np(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / len(X_dev)

        if log or not log:
            stdout.write("\n\ncalculating initial mean loss on dev set")
            stdout.write(": {0}\n".format(initial_loss))
            stdout.write("calculating initial acc on dev set")
            stdout.write(": {0}\n".format(initial_acc))
            stdout.flush()

        prev_loss = initial_loss
        loss_watch_count = -1
        min_change_count = -1

        a0 = learning_rate

        best_loss = initial_loss
        self.model.save_params()
        best_epoch = 0

        for epoch in range(epochs):
            if anneal > 0:
                learning_rate = a0 / ((epoch + 0.0 + anneal) / anneal)
            else:
                learning_rate = a0

            if log:
                stdout.write("\nepoch %d, learning rate %.04f" % (epoch + 1, learning_rate))
                stdout.flush()

            t0 = time.time()
            count = 0

            # use random sequence of instances in the training set (tries to avoid local maxima when training on batches)
            permutation = np.random.permutation(range(len(X)))
            if log:
                stdout.write("\tinstance 1")
            for i in range(len(X)):
                c = i + 1
                if log:
                    stdout.write("\b" * len(str(i)))
                    stdout.write("{0}".format(c))
                    stdout.flush()
                p = permutation[i]
                x_p = X[p]
                d_p = D[p]

                y_p, s_p = self.model.predict(x_p)
                if back_steps == 0:
                    self.model.acc_deltas_np(x_p, d_p, y_p, s_p)
                else:
                    self.model.acc_deltas_bptt_np(x_p, d_p, y_p, s_p, back_steps)

                if i % batch_size == 0:
                    self.model.scale_gradients_for_batch(batch_size)
                    self.model.apply_deltas(learning_rate)

            if len(X) % batch_size > 0:
                mod = len(X) % batch_size
                self.model.scale_gradients_for_batch(mod)
                self.model.apply_deltas(learning_rate)

            loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / loss_sum
            acc = sum([self.compute_acc_np(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / len(X_dev)

            if log:
                stdout.write("\tepoch done in %.02f seconds" % (time.time() - t0))
                stdout.write("\tnew loss: {0}".format(loss))
                stdout.write("\tnew acc: {0}".format(acc))
                stdout.flush()

            if loss < best_loss:
                best_loss = loss
                best_acc = acc
                self.model.save_params()
                best_epoch = epoch

            # make sure we change the RNN enough
            if abs(prev_loss - loss) < min_change:
                min_change_count += 1
            else:
                min_change_count = 0
            if min_change_count > 2:
                print("\n\ntraining finished after {0} epochs due to minimal change in loss".format(epoch + 1))
                break

            prev_loss = loss

        t = time.time() - t_start

        if min_change_count <= 2:
            print("\n\ntraining finished after reaching maximum of {0} epochs".format(epochs))
        print("best observed loss was {0}, acc {1}, at epoch {2}".format(best_loss, best_acc, (best_epoch + 1)))

        print("setting U, V, W to matrices from best epoch")
        self.model.set_best_params()

        return best_loss

if __name__ == "__main__":

    mode = sys.argv[1].lower()
    data_folder = sys.argv[2]
    np.random.seed(2018)

    if mode == "train-lm-rnn":
        '''
        code for training language model.
        change this to different values, or use it to get you started with your own testing class
        '''
        train_size = 25000 # 25000 Change for 2b)
        dev_size = 1000
        vocab_size = 2000

        hdim = int(sys.argv[3])
        lookback = int(sys.argv[4])
        lr = float(sys.argv[5])
        mode = sys.argv[6]

        # get the data set vocabulary
        vocab = pd.read_table(data_folder + "/vocab.wiki.txt", header=None, sep="\s+", index_col=0,
                              names=['count', 'freq'], )
        num_to_word = dict(enumerate(vocab.index[:vocab_size]))
        word_to_num = invert_dict(num_to_word)

        # calculate loss vocabulary words due to vocab_size
        fraction_lost = fraq_loss(vocab, word_to_num, vocab_size)
        print(
            "Retained %d words from %d (%.02f%% of all tokens)\n" % (
            vocab_size, len(vocab), 100 * (1 - fraction_lost)))

        docs = load_lm_dataset(data_folder + '/wiki-train.txt')
        S_train = docs_to_indices(docs, word_to_num, 1, 1)
        X_train, D_train = seqs_to_lmXY(S_train)

        # Load the dev set (for tuning hyperparameters)
        docs = load_lm_dataset(data_folder + '/wiki-dev.txt')
        S_dev = docs_to_indices(docs, word_to_num, 1, 1)
        X_dev, D_dev = seqs_to_lmXY(S_dev)

        # Load the test set
        docs = load_lm_dataset(data_folder + '/wiki-test.txt')
        S_test = docs_to_indices(docs, word_to_num, 1, 1)
        X_test, D_test = seqs_to_lmXY(S_test)

        X_train = X_train[:train_size]
        D_train = D_train[:train_size]
        X_dev = X_dev[:dev_size]
        D_dev = D_dev[:dev_size]

        # q = best unigram frequency from omitted vocab
        # this is the best expected loss out of that set
        q = vocab.freq[vocab_size] / sum(vocab.freq[vocab_size:])

        if mode == "hyperparameter":
            # Best params:
            hidden_dim_params = [25, 50] # 25
            lr_params = [0.5, 0.1, 0.05] # 0.5
            lookback_params = [0, 2, 5]  # 5
            min_loss = None # 4.933136297644713
            best_hidden_dim = None
            best_lr = None
            best_lookback = None
            for hidden_dim_param in hidden_dim_params:
                for lr_param in lr_params:
                    for lookback_param in lookback_params:
                        print("Params: Hidden Dim = {}, Learning Rate = {}, Lookback = {}".format(hidden_dim_param, lr_param, lookback_param))
                        rnn = RNN(vocab_size=vocab_size, hidden_dims=hidden_dim_param, out_vocab_size=vocab_size)
                        runner = Runner(rnn)
                        runner.train(X=X_train, D=D_train, X_dev=X_dev, D_dev=D_dev, learning_rate=lr_param, back_steps=lookback_param)

                        run_loss = runner.compute_mean_loss(X=X_dev, D=D_dev)
                        adjusted_loss = adjust_loss(run_loss, fraction_lost, q)
                        print("Cross Entropy Loss: %.03f" % run_loss)
                        print()
                        if min_loss == None:
                            min_loss = run_loss
                        elif min_loss != None and run_loss < min_loss:
                            best_hidden_dim = hidden_dim_param
                            best_lr = lr_param
                            best_lookback = lookback_param
                            min_loss = run_loss
            print("Best parameters: Hidden Hidden Dim = {}, Learning Rate = {}, Lookback = {}".format(best_hidden_dim, best_lr, best_lookback))
            print("Minimum Loss: {}".format(min_loss))
        else:
            rnn = RNN(vocab_size=vocab_size, hidden_dims=hdim, out_vocab_size=vocab_size)
            runner = Runner(rnn)
            runner.train(X=X_train, D=D_train, X_dev=X_dev, D_dev=D_dev, learning_rate=lr, back_steps=lookback)

            dev_run_loss = runner.compute_mean_loss(X=X_dev, D=D_dev)
            dev_adjusted_loss = adjust_loss(dev_run_loss, fraction_lost, q)

            test_run_loss = runner.compute_mean_loss(X=X_test, D=D_test)
            test_adjusted_loss = adjust_loss(test_run_loss, fraction_lost, q)

            print("Unadjusted (Dev): %.03f" % np.exp(dev_run_loss))
            print("Adjusted for missing vocab (Dev): %.03f" % np.exp(dev_adjusted_loss))
            
            print("Unadjusted (Test): %.03f" % np.exp(test_run_loss))
            print("Adjusted for missing vocab (Test): %.03f" % np.exp(test_adjusted_loss))

            np.save('rnn.U.npy', rnn.U)
            np.save('rnn.V.npy', rnn.V)
            np.save('rnn.W.npy', rnn.W)

    if mode == "train-np-rnn":
        '''
        starter code for parameter estimation.
        change this to different values, or use it to get you started with your own testing class
        '''
        train_size = 10000
        dev_size = 1000
        vocab_size = 2000

        hdim = int(sys.argv[3])
        lookback = int(sys.argv[4])
        lr = float(sys.argv[5])

        # get the data set vocabulary
        vocab = pd.read_table(data_folder + "/vocab.wiki.txt", header=None, sep="\s+", index_col=0,
                              names=['count', 'freq'], )
        num_to_word = dict(enumerate(vocab.index[:vocab_size]))
        word_to_num = invert_dict(num_to_word)

        # calculate loss vocabulary words due to vocab_size
        fraction_lost = fraq_loss(vocab, word_to_num, vocab_size)
        print(
            "Retained %d words from %d (%.02f%% of all tokens)\n" % (
            vocab_size, len(vocab), 100 * (1 - fraction_lost)))

        # load training data
        sents = load_np_dataset(data_folder + '/wiki-train.txt')
        S_train = docs_to_indices(sents, word_to_num, 0, 0)
        X_train, D_train = seqs_to_npXY(S_train)

        X_train = X_train[:train_size]
        Y_train = D_train[:train_size]

        # load development data
        sents = load_np_dataset(data_folder + '/wiki-dev.txt')
        S_dev = docs_to_indices(sents, word_to_num, 0, 0)
        X_dev, D_dev = seqs_to_npXY(S_dev)

        X_dev = X_dev[:dev_size]
        D_dev = D_dev[:dev_size]

        rnn = RNN(vocab_size=vocab_size, hidden_dims=hdim, out_vocab_size=vocab_size)
        runner = Runner(rnn)
        runner.train_np(X=X_train, D=Y_train, X_dev=X_dev, D_dev=D_dev, learning_rate=lr, back_steps=lookback)

        acc = sum([runner.compute_acc_np(x, d) for x, d in zip(X_dev, D_dev)]) / len(X_dev)
        print("Accuracy: %.03f" % acc)

    if mode == "train-np-gru":
        '''
        starter code for parameter estimation.
        change this to different values, or use it to get you started with your own testing class
        '''
        train_size = 10000
        dev_size = 1000
        vocab_size = 2000

        hdim = int(sys.argv[3])
        lookback = int(sys.argv[4])
        lr = float(sys.argv[5])

        # get the data set vocabulary
        vocab = pd.read_table(data_folder + "/vocab.wiki.txt", header=None, sep="\s+", index_col=0,
                              names=['count', 'freq'], )
        num_to_word = dict(enumerate(vocab.index[:vocab_size]))
        word_to_num = invert_dict(num_to_word)

        # calculate loss vocabulary words due to vocab_size
        fraction_lost = fraq_loss(vocab, word_to_num, vocab_size)
        print(
            "Retained %d words from %d (%.02f%% of all tokens)\n" % (
            vocab_size, len(vocab), 100 * (1 - fraction_lost)))

        # load training data
        sents = load_np_dataset(data_folder + '/wiki-train.txt')
        S_train = docs_to_indices(sents, word_to_num, 0, 0)
        X_train, D_train = seqs_to_npXY(S_train)

        X_train = X_train[:train_size]
        Y_train = D_train[:train_size]

        # load development data
        sents = load_np_dataset(data_folder + '/wiki-dev.txt')
        S_dev = docs_to_indices(sents, word_to_num, 0, 0)
        X_dev, D_dev = seqs_to_npXY(S_dev)

        X_dev = X_dev[:dev_size]
        D_dev = D_dev[:dev_size]

        gru = GRU(vocab_size=vocab_size, hidden_dims=hdim, out_vocab_size=vocab_size)
        runner = Runner(gru)
        runner.train(X=X_train, D=D_train, X_dev=X_dev, D_dev=D_dev, learning_rate=lr, back_steps=lookback)

        acc = sum([runner.compute_acc_np(x, d) for x, d in zip(X_dev, D_dev)])

        print("Accuracy: %.03f" % acc)