# Production entrypoint for the Hetzner/Railway deployment.
# Load the complete application/patch chain first, then attach final print/KolayBi/i18n/security patches.
import accounting_runtime as base
import print_return_total_label_patch as print_return_total_label
import print_return_summary_final_patch as print_return_summary_final
import kolaybi_purchase_product_workflow_patch as purchase_product_workflow
import i18n_final_runtime_patch as i18n_final
import security_hardening_patch as security_hardening

app = base.app
