from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

def main():
    analyzer = SentimentIntensityAnalyzer()
    
    print("=" * 50)
    print("Sentiment Analyzer")
    print("=" * 50)
    print("Type text to analyze sentiment")
    print("Press Ctrl+C to quit\n")
    
    while True:
        try:
            text = input("> ")
            
            if text.strip():
                scores = analyzer.polarity_scores(text)
                
                print(f"\n  Positive:  {scores['pos']:.3f}")
                print(f"  Negative:  {scores['neg']:.3f}")
                print(f"  Neutral:   {scores['neu']:.3f}")
                print(f"  Compound:  {scores['compound']:.3f}")
                
                compound = scores['compound']
                if compound >= 0.05:
                    mood = "😊 POSITIVE"
                elif compound <= -0.05:
                    mood = "😞 NEGATIVE"
                else:
                    mood = "😐 NEUTRAL"
                
                print(f"  → {mood}\n")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()