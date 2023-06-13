import textblob
import numpy as np

def removeStopWords(text, stop_words):
    text5 = []
    for w in textblob.TextBlob(text).tokenize().lower():
        if w not in stop_words:
            text5.append(w)
    new_text = ' '.join(text5)
    return new_text 

# create a similarity score function source: https://cdn.aaai.org/AAAI/2006/AAAI06-123.pdf
def sim(s1, s2, nlp):
    # extract open-class words from text ('NN' (noun), 'VB' (verb), 'JJ' (adjective), or 'RB' (adverb))
    DESIRED_POS_TUPLE = ('NNP', 'NNS', 'NN', 'VB', 'VBG', 'VBD', 'JJ', 'RB')
    
    t1 = textblob.TextBlob(s1)
    t2 = textblob.TextBlob(s2)
    
    open_words_text1 = [str(word) for (word, pos) in t1.tags if pos.startswith(DESIRED_POS_TUPLE)]
    open_words_text2 = [str(word) for (word, pos) in t2.tags if pos.startswith(DESIRED_POS_TUPLE)]
    
    # calculate maxSim sum of each open word from text 1
    t1_total = sum(maxSim(w, open_words_text2, nlp) for w in open_words_text1) / len(open_words_text1)

        
    # calculate maxSim sum of each open word from text 2
    t2_total = sum(maxSim(w, open_words_text1, nlp) for w in open_words_text2) / len(open_words_text2)
        
    # return similarity score 
    return 0.5*(t1_total + t2_total)

def maxSim(w1, t2, nlp):
    
    maxsim = 0
    for w2 in t2:
        
        if textblob.TextBlob(w1).tags[0][1] == textblob.TextBlob(w2).tags[0][1]: # same POS
            # Get the word vector
            word1_vector = nlp(w1).vector
            word2_vector = nlp(w2).vector

            # Calculate the cosine similarity
            similarity_score = np.dot(word1_vector, word2_vector) / (np.linalg.norm(word1_vector) * np.linalg.norm(word2_vector))

            if similarity_score >= 1:
                maxsim = similarity_score
                break # perfect match found (no need to check other comparisons)
            elif similarity_score > maxsim:
                maxsim = similarity_score
            else:
                continue
        else:
            # skip calcultion and move to next word
            continue

#         print(f"Similarity score between '{w1}' and '{w2}': {similarity_score}")
    return maxsim

def isRedundantArticle(stop_words, nlp, text1, text2):

    #     # load corpus
    # stop_words = set(nltk.corpus.stopwords.words('english'))
    # nlp = spacy.load('en_core_web_md')

    # remove stop words
    text1 = removeStopWords(text1, stop_words)
    text2 = removeStopWords(text2, stop_words)

    # calculate similarity
    print(f"text1: {text1}")
    print("—" * 100)
    print(f"text2: {text2}")
    print("—" * 100)
    score = sim(text1, text2, nlp)
    print(f"The similarity score between text1 and text2 is {score}")
    print("—" * 100)

    return score > 0.65