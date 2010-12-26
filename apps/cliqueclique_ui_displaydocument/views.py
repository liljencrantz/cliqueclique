import django.shortcuts
import django.template
import django.core.urlresolvers
import cliqueclique_document.models
import cliqueclique_subscription.models
import email.mime.text
import django.http
import utils.smime
import utils.djangosmime
import django.contrib.auth.decorators
import fcdjangoutils.jsonview

@django.contrib.auth.decorators.login_required
def import_document(request):
    msg = request.FILES['file'].read()
    request.user.node.receive(msg)
    msg = utils.smime.message_from_anything(msg)
    container_msg = msg.get_payload()[0]
    update_msg = container_msg.get_payload()[0]
    return django.shortcuts.redirect("cliqueclique_ui_displaydocument.views.display_document", document_id=update_msg['document_id'])

@django.contrib.auth.decorators.login_required
def post_document(request):
    doc = email.mime.text.MIMEText(request.POST['body'])
    for hdr in ('subject', 'parent_document_id'):
        if hdr in request.POST:
            doc.add_header(hdr, request.POST[hdr])

    signed = utils.smime.MIMESigned()
    signed.set_private_key(utils.smime.der2pem(request.user.node.private_key, "PRIVATE KEY"))
    signed.set_cert(utils.smime.der2pem(request.user.node.public_key))
    signed.attach(doc)

    doc = cliqueclique_document.models.Document(content=signed.as_string())
    doc.save()
    sub = cliqueclique_subscription.models.DocumentSubscription(
        node = request.user.node,
        document = doc)
    sub.save()
    for parent in sub.parents.all():
        if not parent.local_is_subscribed:
            parent.local_is_subscribed = True
            parent.save()
    return django.shortcuts.redirect("cliqueclique_ui_displaydocument.views.display_document", document_id=doc.document_id)

@django.contrib.auth.decorators.login_required
def set_document_flags(request, document_id):
    sub = cliqueclique_subscription.models.DocumentSubscription.objects.get(
        node = request.user.node,
        document__document_id = document_id)
    for attr in ('bookmarked', 'read', 'local_is_subscribed'):
        if attr in request.POST:
            attrvalue = request.POST[attr]
        elif attr in request.GET:
            attrvalue = request.GET[attr]
        else:
            continue
        if attrvalue == "toggle":
            value = not getattr(sub, attr)
        elif attrvalue == "true":
            value = True
        else:
            value = False
        setattr(sub, attr, value)
    sub.save()
    return django.shortcuts.redirect("cliqueclique_ui_displaydocument.views.display_document", document_id=sub.document.document_id)

@django.contrib.auth.decorators.login_required
def display_document(request, document_id = None):
    return django.shortcuts.render_to_response(
        'cliqueclique_ui_displaydocument/display.html',
        {'document_id': document_id,
         'request': request,
         'bookmarks': cliqueclique_subscription.models.DocumentSubscription.objects.filter(
                node = request.user.node,
                bookmarked=True).all()},
        context_instance=django.template.RequestContext(request))

@django.contrib.auth.decorators.login_required
def document_as_mime(request, document_id):
    doc = cliqueclique_subscription.models.DocumentSubscription.objects.get(
        node = request.user.node,
        document__document_id=document_id)
    return django.http.HttpResponse(doc.export().as_string(), mimetype="text/plain")


@fcdjangoutils.jsonview.json_view
@django.contrib.auth.decorators.login_required
def document_as_json(request, document_id = None):
    sub = cliqueclique_subscription.models.DocumentSubscription.objects.get(
        node = request.user.node,
        document__document_id = document_id
        )
    return {
        'document_id': document_id,
        'parents': [parent.document.document_id for parent in sub.parents.all()],
        'children': [child.document.document_id for child in sub.children.all()],
        'content': sub.document.as_mime
        }
