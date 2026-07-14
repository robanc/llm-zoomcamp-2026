from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

# Configure OpenTelemetry before importing starter
provider = TracerProvider()
provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("llm-zoomcamp")

from starter import index, client
from rag_helper import RAGBase


class RAGTraced(RAGBase):
    def search(self, query):
        with tracer.start_as_current_span("search"):
            return super().search(query)

    def llm(self, prompt):
        with tracer.start_as_current_span("llm"):
            return super().llm(prompt)

    def rag(self, query):
        with tracer.start_as_current_span("rag"):
            return super().rag(query)


rag = RAGTraced(index=index, llm_client=client)

query = "How does the agentic loop keep calling the model until it stops?"
answer = rag.rag(query)

print("\nANSWER:")
print(answer)