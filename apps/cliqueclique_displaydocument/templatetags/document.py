import django.template
import cliqueclique_subscription.models

register = django.template.Library()

@register.inclusion_tag("cliqueclique_displaydocument/tag/display_document.html", takes_context=True)
def display_document(context, document_id):
    info = {}
    if 'STATIC_URL' in context:
        info['STATIC_URL'] = context['STATIC_URL']
    info['document_subscription'] = cliqueclique_subscription.models.DocumentSubscription.objects.get(
        node = context['user'].node,
        document__document_id=document_id)
    info['body'] = info['document_subscription'].document.as_mime.get_payload()

    return info