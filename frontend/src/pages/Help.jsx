import React from 'react';
import { Link } from 'react-router-dom';

export default function Help() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-6">How it works</h1>

      <div className="prose prose-slate max-w-none space-y-8">
        <section>
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Overview</h2>
          <p className="text-slate-600">
            This system helps you check that a programme (schedule) aligns with your NEC contract.
            You upload your contract, then your programme, and the system compares them and produces
            a validation report you can share with your team or client.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Step 1 — Contract analysis</h2>
          <p className="text-slate-600 mb-2">
            Upload your NEC contract (PDF or Word). The system extracts key information from the contract:
          </p>
          <ul className="list-disc pl-6 text-slate-600 space-y-1">
            <li>Key dates (start, completion, access/possession)</li>
            <li>Scope items — what the contract says must be done</li>
            <li>Constraints — site conditions, access, or other limits</li>
            <li>Programme requirements — when the programme must be submitted and how often it may be revised</li>
          </ul>
          <p className="text-slate-600 mt-2">
            You’ll see a short summary of what was found. When you’re happy, you confirm and continue to the next step.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Step 2 — Programme upload</h2>
          <p className="text-slate-600">
            Upload your programme file (XER from Primavera P6). The system reads the activities and dates
            in the programme. It will then validate this programme against the contract requirements
            identified in step 1.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Step 3 — Validation review</h2>
          <p className="text-slate-600 mb-2">
            Before generating the final report, you’ll see a structured preview:
          </p>
          <ul className="list-disc pl-6 text-slate-600 space-y-1">
            <li>Whether the programme is acceptable at this stage, or what’s missing</li>
            <li>How contract scope and constraints are reflected in the programme</li>
            <li>Required activities and any that are not yet shown in the programme</li>
          </ul>
          <p className="text-slate-600 mt-2">
            Some items are managed through assurance or governance rather than as separate activities;
            the system explains where that applies. You can then proceed to the final report or go back
            to change the contract or programme.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Step 4 — Results and report</h2>
          <p className="text-slate-600">
            The final page shows the executive summary, the acceptability decision, key findings, and
            any required actions. You can download the report as a PDF to keep or share. The filename
            includes the contract name and date so you can easily identify it.
          </p>
        </section>

        <section>
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Your data</h2>
          <p className="text-slate-600">
            Your uploaded documents and analyses are private to your account. You can delete items from
            your history in the dashboard. Data retention is set in your account settings.
          </p>
        </section>
      </div>

      <p className="mt-10">
        <Link to="/dashboard" className="text-amber-600 font-medium hover:text-amber-700">
          Back to dashboard
        </Link>
      </p>
    </div>
  );
}
