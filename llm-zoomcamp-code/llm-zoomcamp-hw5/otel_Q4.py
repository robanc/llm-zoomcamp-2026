import sqlite3

from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)


class SQLiteSpanExporter(SpanExporter):

    def __init__(self, db_path="traces.db"):
        self.conn = sqlite3.connect(db_path)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                name TEXT,
                start_time INTEGER,
                end_time INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost REAL
            )
        """)

        self.conn.commit()

    def export(self, spans):
        for span in spans:
            attrs = dict(span.attributes or {})

            self.conn.execute(
                "INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?)",
                (
                    span.name,
                    span.start_time,
                    span.end_time,
                    attrs.get("input_tokens"),
                    attrs.get("output_tokens"),
                    attrs.get("cost"),
                ),
            )

        self.conn.commit()
        return SpanExportResult.SUCCESS

    def shutdown(self):
        self.conn.close()

    def force_flush(self):
        return True

# Configure OpenTelemetry before importing starter
provider = TracerProvider()
provider.add_span_processor(
    SimpleSpanProcessor(SQLiteSpanExporter("traces.db"))
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
        with tracer.start_as_current_span("llm") as span:
            response = super().llm(prompt)
    
            usage = response.usage
    
            span.set_attribute("input_tokens", usage.input_tokens)
            span.set_attribute("output_tokens", usage.output_tokens)
    
            # Pricing for gpt-5.4-mini (same approach as previous homeworks)
            input_cost = usage.input_tokens * (0.25 / 1_000_000)
            output_cost = usage.output_tokens * (2.00 / 1_000_000)
    
            span.set_attribute("cost", input_cost + output_cost)
    
            return response

    def rag(self, query):
        with tracer.start_as_current_span("rag"):
            return super().rag(query)


rag = RAGTraced(index=index, llm_client=client)

query = "How does the agentic loop keep calling the model until it stops?"
answer = rag.rag(query)

print("\nANSWER:")
print(answer)
