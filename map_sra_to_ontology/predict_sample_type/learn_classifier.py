from optparse import OptionParser
import json
import nltk
from nltk.tokenize import word_tokenize
import numpy as np
from sets import Set
from collections import Counter, defaultdict 

from one_vs_rest_classifier_same_features import OneVsRestClassifier

USE_ONTOLOGY_TERMS = True
USE_NGRAM_FEATURES = True

class FeatureConverter:

    def __init__(self, ngram_vec_scaffold, term_vec_scaffold):
        self.ngram_vec_scaffold = ngram_vec_scaffold
        self.term_vec_scaffold = term_vec_scaffold

    def convert_to_features(self, n_grams, terms):
        feature_vec = np.zeros(len(self.ngram_vec_scaffold) + len(self.term_vec_scaffold))
        c = Counter(n_grams)
        for i, feat in enumerate(self.ngram_vec_scaffold):
            if feat in c:
                feature_vec[i] = c[feat]

        for i, term in enumerate(self.term_vec_scaffold):
            if term in terms:
                feature_vec[i + len(self.ngram_vec_scaffold)] = 1

        return feature_vec


def learn_model(
    algorithm, 
    training_set, 
    sample_to_ngrams, 
    sample_to_predicted_terms, 
    num_features_per_class, 
    doc_freq_thresh, 
    balance_classes, 
    cvcl_og):
    """
    Args:
        training_set: list of tuples where first element of tuple is a dictionary of
        key-value pairs and the second element is a string with the class name
    """
    sample_attributes = []
    labels = []
    sample_accs = []

    label_freqs = Counter([t[1] for t in training_set])
    print label_freqs

    for t in training_set:
        sample_attributes.append(t[0])
        labels.append(t[1])
        sample_accs.append(t[2])

    ngram_vec_scaffold = ngram_features(sample_attributes, sample_accs, sample_to_ngrams, doc_freq_thresh)
    term_vec_scaffold = ont_term_features(sample_accs, sample_to_predicted_terms, doc_freq_thresh)
    vectorizer = FeatureConverter(ngram_vec_scaffold, term_vec_scaffold)

    feature_vecs = [vectorizer.convert_to_features(sample_to_ngrams[x], sample_to_predicted_terms[x]) for x in sample_accs]

    classif = OneVsRestClassifier(
        "logistic_regression_l1", 
        ngram_vec_scaffold, 
        term_vec_scaffold, 
        cvcl_og, 
        num_features_per_class=num_features_per_class, 
        use_predicted_term_rules=True)
    classif.fit(feature_vecs, labels)
    return vectorizer, classif


def get_ngrams_from_tag_to_val(tag_to_val):
    N = 2
    ngrams = []
    for tag, val in tag_to_val.iteritems():
        for n in range(1, N+1):
            ngrams += [x.lower()  for x in get_ngrams(tag, n)[0]]
            ngrams += [x.lower() for x in get_ngrams(val, n)[0]]
    ngrams = [x for x in ngrams if len(x) > 1]
    return ngrams

def get_samples_to_ngram(dataset):
    print "building n-gram index..."
    sample_to_ngrams = defaultdict(lambda: [])
    for d in dataset:
        sample_to_ngrams[d[2]] = get_ngrams_from_tag_to_val(d[0])
    return sample_to_ngrams




def ngram_features(sample_attributes, sample_accs, sample_to_ngrams, doc_freq_thresh):
    if not USE_NGRAM_FEATURES:
        return []

    bag_of_grams = Set()
    n_gram_to_count = defaultdict(lambda: 0)
    n_gram_to_doc_freq = defaultdict(lambda: 0)

    for i, doc in enumerate(sample_attributes):
        n_grams = sample_to_ngrams[sample_accs[i]]
        for gram, count in Counter(n_grams).iteritems():
            n_gram_to_count[gram] += count
            n_gram_to_doc_freq[gram] += 1

    print "Len of n-grams before trim: %d" % len(Set(n_gram_to_count.keys()))
    bag_of_n_grams = Set([x for x in n_gram_to_count.keys() if n_gram_to_doc_freq[x] > doc_freq_thresh])
    #bag_of_n_grams = Set([x for x in bag_of_n_grams if float(n_gram_to_doc_freq[x])/len(sample_attributes) < 0.6])

    stop_words = Set()
    with open("stop_words.09-23-16.json", "r") as f:
        for l in f:
            stop_words.add(l.strip())
    bag_of_n_grams = bag_of_n_grams.difference(stop_words)
    print "Len of n-grams after stop words: %d" % len(bag_of_n_grams)

    #bag_of_n_grams = Set(n_gram_to_count.keys())
    vec_scaffold = list(bag_of_n_grams)
    print "The vector scaffold is: %s" % vec_scaffold

    return vec_scaffold




def ont_term_features(sample_accs, sample_to_predicted_terms, doc_freq_thresh):
    if not USE_ONTOLOGY_TERMS:
        return []

    bag_of_ont_terms = Set()
    term_to_doc_freq = defaultdict(lambda: 0)

    for sample in sample_accs:
        terms = sample_to_predicted_terms[sample]
        for term, count in Counter(terms).iteritems():
            term_to_doc_freq[term] += 1

    bag_of_terms = Set([x for x in term_to_doc_freq.keys() if term_to_doc_freq[x] > doc_freq_thresh])
    term_vec_scaffold = list(bag_of_terms)

    print "The ontology term features are: %s" % term_vec_scaffold
    return term_vec_scaffold

def get_ngrams(text, n):

    delimiters = ["_", "/", "-"]
    for delim in delimiters:
        text = text.replace(delim, " ")

    words = nltk.word_tokenize(text)
    new_words = []
    for word in words:
        if word == "``":
            new_words.append('"')
        elif word == "''":
            new_words.append('"')
        else:
            new_words.append(word)
    words = new_words
    #words = text.split()

    if not words:
        return [], []

    text_i = 0
    curr_word = words[0]
    word_i = 0
    word_char_i = 0

    word_to_indices = defaultdict(lambda: [])
    for text_i in range(len(text)):

        if word_char_i == len(words[word_i]):
            word_i += 1
            word_char_i = 0
        if word_i == len(words):
            break

        if text[text_i] ==  words[word_i][word_char_i]:
            word_to_indices[word_i].append(text_i)
            word_char_i += 1
        text_i += 1

    n_grams = []
    intervals = []
    for i in range(0, len(words)-n+1):
        grams = words[i:i+n]
        text_char_begin = word_to_indices[i][0]
        text_char_end = word_to_indices[i+n-1][-1]
        n_gram = text[text_char_begin: text_char_end+1]
        n_grams.append(n_gram)
        intervals.append((text_char_begin, text_char_end+1))

    return n_grams, intervals


def get_samples_to_mappings(matches_file, ogs):

    print "loading sample to predicted ontology term mappings..."
    sample_to_predicted_terms = defaultdict(lambda: Set())
    sample_to_real_val_props = {}

    with open(matches_file, "r") as f:
        j = json.load(f)
        for sample_acc, map_data in j.iteritems():
            mapped_term_ids = [x["term_id"] for x in map_data["mapped_terms"]]
            term_in_onts = False
            for term in mapped_term_ids:
                for og in ogs:
                    if term in og.mappable_term_ids:
                        sample_to_predicted_terms[sample_acc].add(term)
                        break
            real_val_props = [{"property_id":x["property_id"], "unit_id":x["unit_id"], "value":x["value"]} for x in map_data["real_value_properties"]]
            sample_to_real_val_props[sample_acc] = real_val_props

    for sample_acc, predicted_terms in sample_to_predicted_terms.iteritems():
        sup_terms = Set()
        for og in ogs:
            for term in predicted_terms:
                sup_terms.update(og.recursive_relationship(term, ['is_a', 'part_of']))
        sample_to_predicted_terms[sample_acc].update(sup_terms)

    return sample_to_predicted_terms, sample_to_real_val_props


