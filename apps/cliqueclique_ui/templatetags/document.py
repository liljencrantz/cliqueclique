import django.template
import cliqueclique_subscription.models
import cliqueclique_node.models
import settings
import utils.smime
import cliqueclique_ui_document.secure_id

register = django.template.Library()

@register.inclusion_tag("cliqueclique_ui/tag/display_document.html", takes_context=True)
def display_document(context, document_id):
    info = {}
    if 'security_context' in context:
        info['security_context'] = context['security_context']
    if 'STATIC_URL' in context:
        info['STATIC_URL'] = context['STATIC_URL']
    info['document_subscription'] = cliqueclique_subscription.models.DocumentSubscription.objects.get(
        node = context['user'].node,
        document__document_id=cliqueclique_ui_document.secure_id.secure_id_to_id(document_id))
    doc = info['document_subscription'].document.as_mime

    if doc.get_content_type() == 'multipart/signed':
        cert = doc.verify()[0]
        doc = doc.get_payload()[0]

        data = utils.smime.cert_get_data(cert)
        info['document_signature'] = cliqueclique_node.models.Node.node_id_from_public_key(cert)
        info['document_signature_name'] = data['name']
        info['document_signature_address'] = data['address']

    info['document_id'] = document_id
    info['document'] = doc
    info['document_body'] = doc.get_payload()

    return info

@register.filter
def formatid(id):
    if id is None:
        return 'None'
    return id[:settings.CLIQUECLIQUE_HASH_PRINT_LENGTH]

