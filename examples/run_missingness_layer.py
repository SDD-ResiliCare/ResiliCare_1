from resilicare import prepare_history_context, weighted_risk_signal

patient = {
    "has_prior_history": False,
    "history_features": {"comorbidity_burden": 0.9, "medication_risk": 0.7},
}
context = prepare_history_context(patient)

print(context["ui_notice"])
print("Scorer history features:", context["history_features"])
print("Scorer weights:", context["scorer_weights"])
print("Combined risk signal:", weighted_risk_signal(0.8, None, context))
