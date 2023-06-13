import tweepy
from tweepy import client
import config
import datetime
import pandas as pd
import psycopg2
import preprocessor as p
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.sentiment.util import *
import numpy as np
import time
from newscatcherapi import NewsCatcherApiClient
import similarity_score
import spacy

# Authenticate using OAuth2.0 Twitter
# OUTPUT: TYPE(dataframe)
def collectData():
    # initialize root dataframe
    df = pd.DataFrame()
    
    newscatcherapi = NewsCatcherApiClient(x_api_key=config.NEWS_CATCHER_KEY)   
    q = ["Tesla"]

    today = datetime.datetime.today()
    yesterday = today - datetime.timedelta(days=1)

    y_date_str = yesterday.strftime("%Y/%m/%d")
    t_date_str = today.strftime("%Y/%m/%d")

    try:
        response = newscatcherapi.get_search(q=q[0],
                                                lang='en',
                                                countries='US',
                                                page_size=5,
                                                sort_by="relevancy",
                                                from_= y_date_str,
                                                to_= t_date_str,
                                                published_date_precision="full"
                                            )
        articles = response["articles"]
        # print(len(articles))
        for article in articles:
            data = {}
            data["company"] = q[0]
            data["title"] = article["title"]
            data["author"] = article["author"]
            data["published_date"] = article["published_date"]
            data["summary"] = article["summary"]
            data["rank"] = article["rank"]
            data["id"] = article["_id"]
            data["url"] = article["link"]

            # convert dictionary to a dataframe and concatenate it to df
            row_df = pd.DataFrame(data, index=[0])
            df = pd.concat([df, row_df])

    except Exception as e:
        print(e)
        print()
    df.to_csv("beforePreProcessing.csv")

    return df

# source: https://archive.is/9ApqZ#selection-1633.90-1645.43
# Using a library to deal with preprocessing
def preprocessing(row, col_name):
    print(row)
    text = str(row[col_name])

    # Remove special characters
    text = text.replace("$", "").replace("&", "").replace("amp", "").replace(";", "").replace("\'", "").replace("\n", " ")

    print(row)
    print(f"Text: {text}")
    # text = p.clean(text)
    return text

def deleteRedundantArticles(df):

    df_new_articles = pd.DataFrame({}, columns = df.columns)

    # Inserting first row into the new dataframeSeries to a DataFrame
    df_row = pd.DataFrame(data=[df.iloc[0].tolist()], columns=df.columns)
    df_new_articles = pd.concat([df_new_articles, df_row]) # add first row

    # load corpus
    stop_words = set(nltk.corpus.stopwords.words('english'))
    nlp = spacy.load('en_core_web_md')

    # Iterate over the remaining rows
    for index, row in df.iloc[1:].iterrows():
        isRedundant = similarity_score.isRedundantArticle(stop_words, nlp, row["clean_summary"], df_new_articles.iloc[-1]["clean_summary"])

        if not isRedundant:
            # insert row into new dataframe
            df_row = pd.DataFrame(data=[row.tolist()], columns=df.columns)
            df_new_articles = pd.concat([df_new_articles, df_row])
        else:
            continue

    unique_article_percentage = round(100*len(df_new_articles)/len(df), 2)
    print(f"Unique articles: {len(df_new_articles)}")
    print(f"Collected Articles: {len(df)}")
    print(f"Unique Percentage:  {unique_article_percentage}")
    return df_new_articles

# source: https://archive.is/9ApqZ#selection-2157.94-2157.818
def analysis(df):
    print("Analyzing data...")
    print()
    #Sentiment Analysis
    SIA = SentimentIntensityAnalyzer()

    # Applying Model, Variable Creation
    df['Polarity Score']=df["summary"].apply(lambda x:SIA.polarity_scores(x)['compound'])
    df['Neutral Score']=df["summary"].apply(lambda x:SIA.polarity_scores(x)['neu'])
    df['Negative Score']=df["summary"].apply(lambda x:SIA.polarity_scores(x)['neg'])
    df['Positive Score']=df["summary"].apply(lambda x:SIA.polarity_scores(x)['pos'])

    # Converting 0 to 1 Decimal Score to a Categorical Variable
    df['Sentiment']=''
    df.loc[df['Polarity Score']>0,'Sentiment']='Positive'
    df.loc[df['Polarity Score']==0,'Sentiment']='Neutral'
    df.loc[df['Polarity Score']<0,'Sentiment']='Negative'
    return df

def insert():
    # create database
    DB_NAME = "news"
    DB_USER = "zachmoss"
    DB_PASS = ""
    DB_HOST = "127.0.0.1"
    DB_PORT = "5432"
    conn = ""
    cur = ""
    
    # connect to database
    try:
        conn = psycopg2.connect(database=DB_NAME,
                                user=DB_USER,
                                password=DB_PASS,
                                host=DB_HOST,
                                port=DB_PORT)
        print("Database connected successfully")
    except:
        print("Database not connected successfully")
    
    # create table
    try:
        cur = conn.cursor()  # creating a cursor

        # executing queries to create table
        cur.execute("""
        CREATE TABLE News
        (
            COMPANY VARCHAR(10),
            TITLE VARCHAR,
            SUMMARY VARCHAR,
            AUTHOR VARCHAR,
            CREATED_AT VARCHAR,
            RANK INT,
            URL VARCHAR,
            POLARITY_SCORE NUMERIC(4,3),
            POSITIVE_SCORE NUMERIC(4,3),
            NEUTRAL_SCORE NUMERIC(4,3),
            NEGATIVE_SCORE NUMERIC(4,3),
            SENTIMENT VARCHAR
        )
        """)
        
        # commit the changes
        conn.commit()
        print("Table Created successfully")
    except Exception as e:
        print("An exception occurred:", str(e))
        print("Table not created")
    
    # inserting rows into database
    for index, row in df.iterrows():
        try:
            # check if entry exists in database
            q = f"""
            SELECT 
                *
            FROM 
                news
            WHERE 
                title = '{row['clean_title']}'
                AND author = '{row['clean_author']}'
            """
            cur.execute(q)
            rows = cur.fetchall()
            print(rows)
            print('Data fetched successfully')

            if not rows:
                print("inserting")
                cur.execute("""
                    INSERT INTO news (COMPANY, TITLE, SUMMARY, AUTHOR, CREATED_AT, RANK, URL,
                                    POLARITY_SCORE, NEUTRAL_SCORE, NEGATIVE_SCORE, POSITIVE_SCORE,
                                    SENTIMENT)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(row['company']),
                        str(row['clean_title']),
                        str(row['clean_summary']),
                        str(row['clean_author']),
                        str(row['published_date']),
                        int(row['rank']),
                        str(row["url"]),
                        float(row['Polarity Score']),
                        float(row['Neutral Score']),
                        float(row['Negative Score']),
                        float(row['Positive Score']),
                        str(row['Sentiment'])
                    )
                )
                conn.commit()
                print('Data inserted successfully')
            else:
                print('Entry already exists in the database')
        except Exception as e:
            print(f'Exception occurred: {str(e)}')
            conn.rollback()
    conn.close()

def outputFile(df):
    # reconnect to database
    DB_NAME = "news"
    DB_USER = "zachmoss"
    DB_PASS = ""
    DB_HOST = "127.0.0.1"
    DB_PORT = "5432"
    conn = ""
    cur = ""

    try:
        conn = psycopg2.connect(database=DB_NAME,
                                user=DB_USER,
                                password=DB_PASS,
                                host=DB_HOST,
                                port=DB_PORT)
        print("Database connected successfully")
    except:
        print("Database not connected successfully")

    # export to csv
    try:
        cur = conn.cursor()  # creating a cursor
 
        # executing queries to create table
        cur.execute("""
        COPY news TO '/Users/zachmoss/Twitter Project/finalOutput.csv' WITH DELIMITER ',' CSV HEADER;
        """)
        
        # commit the changes
        conn.commit()
        print("CSV Created successfully")
    except Exception as e:
        print("An exception occurred:", str(e))
        print("CSV not created")
    conn.close()

# store tweets in a database
if __name__ == "__main__":
    df = collectData()

    print("Preprecosseing Complete")
    df['clean_summary'] = df.apply(lambda x: preprocessing(x, "summary"), axis=1)
    df["clean_title"] = df.apply(lambda y: preprocessing(y, "title"), axis=1)
    df["clean_author"] = df.apply(lambda z: preprocessing(z, "author"), axis=1)

    # df['clean_tweet'] = [preprocessing(row) for row in df]
    print()

    print("Deleteing Redundant Articles")
    df = deleteRedundantArticles(df)

    df = analysis(df)
    print("Analysis Complete!")
    print()

    print("Inserting Data!")
    insert()

    outputFile(df)