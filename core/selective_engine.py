class SelectiveTranscriptionEngine:
    """
    Stage 4: Calibrated Selective Prediction Engine
    Formulated in FewDSR Section 5 (Stage 4).
    
    Instead of outputting silent hallucinations or incorrect guesses, 
    tokens falling below the calibrated uncertainty threshold tau are
    explicitly tagged as [UNCERTAIN: word].
    """
    def __init__(self, confidence_threshold=0.70):
        self.tau = confidence_threshold

    def process_tokens(self, tokens_with_conf, custom_tau=None):
        threshold = custom_tau if custom_tau is not None else self.tau
        
        output_words = []
        html_badges = []
        accepted_count = 0
        total_tokens = len(tokens_with_conf)
        
        for item in tokens_with_conf:
            word = item["word"]
            conf = item["calibrated_conf"]
            raw_conf = item.get("raw_conf", conf)
            grounded = item.get("grounded", True)
            
            if not grounded:
                # Suppressed hallucination
                output_words.append(f"[HALLUCINATION_SUPPRESSED]")
                html_badges.append(f"<span style='background-color:#ffcccc; color:#990000; padding:2px 6px; border-radius:4px; font-weight:bold;' title='Suppressed by Acoustic-Null Check'>[SUPPRESSED]</span>")
            elif conf >= threshold:
                accepted_count += 1
                output_words.append(word)
                html_badges.append(f"<span style='background-color:#d4edda; color:#155724; padding:2px 6px; border-radius:4px;' title='Calibrated Conf: {conf*100:.1f}%'>{word}</span>")
            else:
                output_words.append(f"[UNCERTAIN: {word}]")
                html_badges.append(f"<span style='background-color:#fff3cd; color:#856404; padding:2px 6px; border-radius:4px; border:1px dashed #ffeeba;' title='Calibrated Conf: {conf*100:.1f}% (Below Threshold {threshold*100:.0f}%)'>[UNCERTAIN: {word}]</span>")
                
        coverage = (accepted_count / total_tokens * 100) if total_tokens > 0 else 0.0
        
        return {
            "transcription_text": " ".join(output_words),
            "html_rendered": " ".join(html_badges),
            "coverage_percent": round(coverage, 1),
            "total_tokens": total_tokens,
            "accepted_tokens": accepted_count,
            "uncertain_tokens": total_tokens - accepted_count
        }
